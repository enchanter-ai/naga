#!/usr/bin/env python3
"""Build "THE LAST TORCH" end to end: render, edit, encode, package.

    python3 capcut/make.py all          # everything
    python3 capcut/make.py render       # voxel frames -> out/raw/
    python3 capcut/make.py edit         # transitions + type -> out/frames/
    python3 capcut/make.py encode       # ffmpeg -> out/*.mp4
    python3 capcut/make.py package      # CapCut import bundle

Python 3.8+ stdlib only. ffmpeg is needed for `encode` alone; every other
stage is pure Python and degrades to a PNG sequence without it.
"""

import argparse
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capcut.pipeline import edit as E
from capcut.pipeline import render as R
from capcut.pipeline.pngio import write_png
from capcut.pipeline.shots import Scene
from capcut.pipeline.world import World

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = os.path.join(HERE, "scene.json")
OUT = os.path.join(HERE, "out")
RAW = os.path.join(OUT, "raw")
FRAMES = os.path.join(OUT, "frames")
CLEAN = os.path.join(OUT, "frames_clean")

_W = {}


def _init_worker(seed):
    world = World(seed=seed)
    _W["world"] = world
    _W["boxes"] = R.build_static_boxes(world)


def _render_one(job):
    shot_id, i, n, dur, width, height, tod_spec, cam_state, far = job
    world, boxes = _W["world"], _W["boxes"]
    pos, yaw, pitch, fov = cam_state
    cam = R.Camera(pos, yaw, pitch, fov)
    tod = R.resolve_tod(tod_spec[0], tod_spec[1])
    t = (i / float(n)) * dur
    frame = R.render_frame(world, boxes, cam, tod, width, height, t,
                           far=far, flicker=R.torch_flicker(t))
    E.save_raw(os.path.join(RAW, shot_id, "%05d.raw" % i), frame)
    return shot_id, i


def cmd_render(args):
    world = World(seed=json.load(open(SCENE)).get("seed", 20260901))
    scene = Scene(SCENE, world)
    jobs = []
    for shot in scene.shots:
        os.makedirs(os.path.join(RAW, shot.id), exist_ok=True)
        n = shot.frames(scene.fps)
        for i in range(n):
            u = i / float(max(1, n - 1))
            cam = shot.camera(u)
            jobs.append((shot.id, i, n, shot.duration, scene.width,
                         scene.height, (shot.tod, shot.ease(u)),
                         (cam.pos, cam.yaw, cam.pitch, cam.fov), args.far))
    todo = [j for j in jobs
            if args.force or not os.path.exists(
                os.path.join(RAW, j[0], "%05d.raw" % j[1]))]
    print("render: %d frames (%d already done) on %d workers"
          % (len(todo), len(jobs) - len(todo), args.jobs))
    if not todo:
        return
    t0 = time.time()
    done = 0
    with mp.Pool(args.jobs, initializer=_init_worker,
                 initargs=(scene.seed,)) as pool:
        for _ in pool.imap_unordered(_render_one, todo, chunksize=1):
            done += 1
            if done % 10 == 0 or done == len(todo):
                el = time.time() - t0
                rate = done / el
                eta = (len(todo) - done) / rate if rate else 0
                print("  %d/%d  %.2f fps  eta %ds"
                      % (done, len(todo), rate, int(eta)), flush=True)
    print("render done in %.1fs" % (time.time() - t0))


def _shot_raws(scene, shot):
    d = os.path.join(RAW, shot.id)
    n = shot.frames(scene.fps)
    return [os.path.join(d, "%05d.raw" % i) for i in range(n)]


def cmd_edit(args):
    world = World(seed=json.load(open(SCENE)).get("seed", 20260901))
    scene = Scene(SCENE, world)
    for d in (FRAMES, CLEAN):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
    W, H = scene.width, scene.height
    fps = scene.fps

    # 1. Composite each shot at render resolution: fades, then type is
    #    deferred to output resolution below.
    shot_frames = []
    for si, shot in enumerate(scene.shots):
        paths = _shot_raws(scene, shot)
        n = len(paths)
        fi = int(shot.fade_in * fps)
        fo = int(shot.fade_out * fps)
        buf = []
        for i, p in enumerate(paths):
            f = E.load_raw(p, W, H)
            if fi and i < fi:
                E.fade_to(f, 1.0 - i / float(fi))
            if fo and i >= n - fo:
                E.fade_to(f, (i - (n - fo) + 1) / float(fo))
            buf.append((f, si, i, n))
        shot_frames.append(buf)

    # 2. Splice with transitions.
    timeline = []
    edl = []
    for si, buf in enumerate(shot_frames):
        tr = scene.transition_after(si) if si < len(shot_frames) - 1 else None
        start = len(timeline)
        if si == 0:
            head = buf
        else:
            head = buf[pending_head:]
        pending_head = 0
        if tr:
            d = tr["frames"]
            body, tail = head[:-d], head[-d:]
            timeline.extend(body)
            nxt = shot_frames[si + 1]
            for k in range(d):
                a, b = tail[k][0], nxt[k][0]
                blended = E.dissolve(a, b, (k + 1) / float(d + 1))
                # Type from the outgoing shot wins across the dissolve.
                timeline.append((blended, si, tail[k][2], tail[k][3]))
            pending_head = d
        else:
            timeline.extend(head)
        edl.append({"shot": scene.shots[si].id, "start_frame": start,
                    "end_frame": len(timeline)})

    # 3. Upscale, draw type at output resolution, write PNGs.
    up = scene.upscale
    total = len(timeline)
    for out_i, (f, si, i, n) in enumerate(timeline):
        big = f.scale_nearest(up)
        # Clean pass first: the per-shot clips ship without burned-in type so
        # captions stay editable in CapCut. Type goes on the master only.
        write_png(os.path.join(CLEAN, "%05d.png" % out_i), big,
                  level=args.png_level)
        shot = scene.shots[si]
        if shot.title:
            a = E.envelope(i, n, fps, hold_in=0.7, hold_out=0.7,
                           delay=0.9, life=3.0)
            E.draw_title(big, shot.title, shot.subtitle, a)
        if shot.caption:
            a = E.envelope(i, n, fps, hold_in=0.35, hold_out=0.45,
                           delay=0.55)
            E.draw_caption(big, shot.caption, a)
        write_png(os.path.join(FRAMES, "%05d.png" % out_i), big, level=args.png_level)
        if out_i % 25 == 0:
            print("  edit %d/%d" % (out_i, total), flush=True)

    # 4. End card.
    ec = scene.spec.get("end_card")
    idx = total
    if ec:
        ecn = int(ec["duration"] * fps)
        for k in range(ecn):
            a = min(1.0, k / float(max(1, int(fps * 0.5))))
            a = min(a, max(0.0, (ecn - k) / float(max(1, int(fps * 0.5)))))
            card = E.end_card(scene.out_width, scene.out_height,
                              ec["line1"], ec.get("line2"), a)
            write_png(os.path.join(FRAMES, "%05d.png" % idx), card,
                      level=args.png_level)
            write_png(os.path.join(CLEAN, "%05d.png" % idx), card,
                      level=args.png_level)
            idx += 1
        edl.append({"shot": "05_end_card", "start_frame": total,
                    "end_frame": idx})

    with open(os.path.join(OUT, "edl.json"), "w") as fh:
        json.dump({"fps": fps, "width": scene.out_width,
                   "height": scene.out_height, "total_frames": idx,
                   "cuts": edl}, fh, indent=2)
    _write_srt(scene, edl, os.path.join(OUT, "captions.srt"))
    print("edit done: %d frames -> %s" % (idx, FRAMES))


def _tc(frame, fps):
    ms = int(round(frame / float(fps) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _write_srt(scene, edl, path):
    """Captions as SRT — the format CapCut imports directly."""
    lines = []
    idx = 1
    by_id = {c["shot"]: c for c in edl}
    for shot in scene.shots:
        text = shot.caption or (shot.title if not shot.caption else None)
        if not text:
            continue
        cut = by_id.get(shot.id)
        if not cut:
            continue
        start = cut["start_frame"] + int(0.55 * scene.fps)
        end = min(cut["end_frame"], start + int(2.9 * scene.fps))
        lines.append("%d\n%s --> %s\n%s\n"
                     % (idx, _tc(start, scene.fps), _tc(end, scene.fps), text))
        idx += 1
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def cmd_encode(args):
    ff = find_ffmpeg()
    if not ff:
        print("ffmpeg not found; frames remain in %s" % FRAMES)
        return 1
    world = World(seed=json.load(open(SCENE)).get("seed", 20260901))
    scene = Scene(SCENE, world)
    master = os.path.join(OUT, "the_last_torch_1280x720.mp4")
    cmd = [ff, "-y", "-framerate", str(scene.fps), "-i",
           os.path.join(FRAMES, "%05d.png"),
           "-c:v", "libx264", "-preset", "slow", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", master]
    print(" ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.STDOUT)
    print("wrote", master, "%.1f MB" % (os.path.getsize(master) / 1e6))

    # Per-shot clips: CapCut edits better with separate takes on the timeline.
    edl = json.load(open(os.path.join(OUT, "edl.json")))
    clips = os.path.join(OUT, "clips")
    os.makedirs(clips, exist_ok=True)
    for cut in edl["cuts"]:
        dst = os.path.join(clips, "%s.mp4" % cut["shot"])
        n = cut["end_frame"] - cut["start_frame"]
        sub = [ff, "-y", "-framerate", str(scene.fps),
               "-start_number", str(cut["start_frame"]),
               "-i", os.path.join(CLEAN, "%05d.png"),
               "-frames:v", str(n),
               "-c:v", "libx264", "-preset", "slow", "-crf", "19",
               "-pix_fmt", "yuv420p", dst]
        subprocess.run(sub, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)
        print("  clip", os.path.basename(dst), n, "frames")

    poster = os.path.join(OUT, "poster.png")
    shutil.copy(os.path.join(FRAMES, "%05d.png" % int(scene.fps * 12)), poster)
    return 0


def cmd_package(args):
    from capcut.package import build_package
    world = World(seed=json.load(open(SCENE)).get("seed", 20260901))
    scene = Scene(SCENE, world)
    build_package(scene, OUT)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["render", "edit", "encode", "package",
                                      "all"])
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--far", type=float, default=150.0)
    ap.add_argument("--png-level", type=int, default=6)
    ap.add_argument("--force", action="store_true",
                    help="re-render frames that already exist")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.stage in ("render", "all"):
        cmd_render(args)
    if args.stage in ("edit", "all"):
        cmd_edit(args)
    if args.stage in ("encode", "all"):
        cmd_encode(args)
    if args.stage in ("package", "all"):
        cmd_package(args)


if __name__ == "__main__":
    main()
