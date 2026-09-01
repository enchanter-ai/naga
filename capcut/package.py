"""Build the CapCut hand-off package.

Three interchange layers, most reliable first:

1. `clips/*.mp4` + `captions.srt` — plain media and a standard subtitle
   file. Every CapCut build on every platform imports these.
2. `the_last_torch.edl` — CMX3600 edit decision list, for round-tripping
   the cut into an NLE that speaks EDL.
3. `capcut_draft/` — a generated CapCut desktop draft folder.

Layer 3 is BEST-EFFORT. CapCut's draft schema is proprietary, undocumented
and versioned per release; this generator was written without a CapCut
install to validate against, so treat it as a starting point and fall back
to layer 1 if your CapCut build rejects it. Nothing else in the pipeline
depends on it.
"""

import hashlib
import json
import os
import shutil
import time
import uuid


def _uid(*parts):
    """Deterministic uppercase UUID-shaped id, so rebuilds are diffable."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()
    return ("%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20],
                                h[20:32])).upper()


def _us(frames, fps):
    """Frames -> microseconds, CapCut's timeline unit."""
    return int(round(frames / float(fps) * 1_000_000))


def _tc(frame, fps):
    f = int(frame % fps)
    total = int(frame // fps)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return "%02d:%02d:%02d:%02d" % (h, m, s, f)


def write_edl(scene, edl, path):
    """CMX3600 edit decision list for the assembled cut."""
    fps = edl["fps"]
    out = ["TITLE: %s" % scene.title, "FCM: NON-DROP FRAME", ""]
    rec = 0
    for i, cut in enumerate(edl["cuts"], start=1):
        n = cut["end_frame"] - cut["start_frame"]
        out.append("%03d  AX       V     C        %s %s %s %s"
                   % (i, _tc(0, fps), _tc(n, fps), _tc(rec, fps),
                      _tc(rec + n, fps)))
        out.append("* FROM CLIP NAME: %s.mp4" % cut["shot"])
        out.append("")
        rec += n
    with open(path, "w") as fh:
        fh.write("\n".join(out))


def write_shotlist(scene, edl, path):
    fps = edl["fps"]
    rows = ["| # | Shot | In | Out | Sec | Light | Move | On-screen text |",
            "|---|------|----|-----|-----|-------|------|----------------|"]
    by_id = {s.id: s for s in scene.shots}
    for i, cut in enumerate(edl["cuts"], start=1):
        n = cut["end_frame"] - cut["start_frame"]
        shot = by_id.get(cut["shot"])
        light = shot.tod if shot else "-"
        light = " -> ".join(light) if isinstance(light, list) else light
        move = (shot.note if shot else "End card.")
        text = ((shot.title or shot.caption or "") if shot
                else scene.spec["end_card"]["line1"])
        rows.append("| %d | `%s` | %s | %s | %.2f | %s | %s | %s |"
                    % (i, cut["shot"], _tc(cut["start_frame"], fps),
                       _tc(cut["end_frame"], fps), n / float(fps), light,
                       move, text))
    with open(path, "w") as fh:
        fh.write("# %s — shot list\n\n%s\n\n%s\n"
                 % (scene.title, scene.logline, "\n".join(rows)))


def build_draft(scene, edl, clip_dir, out_dir):
    """Generate a CapCut desktop draft folder. Best-effort; see module docs."""
    os.makedirs(out_dir, exist_ok=True)
    fps = edl["fps"]
    total_frames = edl["total_frames"]
    draft_id = _uid(scene.title, "draft")

    videos, segments, texts, text_segments = [], [], [], []
    rec = 0
    by_id = {s.id: s for s in scene.shots}
    for cut in edl["cuts"]:
        n = cut["end_frame"] - cut["start_frame"]
        mid = _uid(cut["shot"], "video")
        path = os.path.join(clip_dir, "%s.mp4" % cut["shot"])
        videos.append({
            "id": mid,
            "type": "video",
            "material_name": "%s.mp4" % cut["shot"],
            "path": os.path.abspath(path),
            "duration": _us(n, fps),
            "width": edl["width"],
            "height": edl["height"],
            "has_audio": False,
            "crop": {"lower_left_x": 0.0, "lower_left_y": 1.0,
                     "lower_right_x": 1.0, "lower_right_y": 1.0,
                     "upper_left_x": 0.0, "upper_left_y": 0.0,
                     "upper_right_x": 1.0, "upper_right_y": 0.0},
            "crop_ratio": "free",
            "crop_scale": 1.0,
        })
        segments.append({
            "id": _uid(cut["shot"], "seg"),
            "material_id": mid,
            "target_timerange": {"start": _us(rec, fps), "duration": _us(n, fps)},
            "source_timerange": {"start": 0, "duration": _us(n, fps)},
            "speed": 1.0,
            "volume": 1.0,
            "visible": True,
            "render_index": 0,
            "clip": {"alpha": 1.0, "flip": {"horizontal": False, "vertical": False},
                     "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0},
                     "transform": {"x": 0.0, "y": 0.0}},
            "extra_material_refs": [],
        })

        shot = by_id.get(cut["shot"])
        caption = shot.caption if shot else None
        if caption:
            tid = _uid(cut["shot"], "text")
            texts.append({
                "id": tid,
                "type": "text",
                "content": caption,
                "font_size": 8.0,
                "text_color": "#FFFFFF",
                "alignment": 1,
                "has_shadow": True,
                "background_alpha": 0.45,
                "background_color": "#000000",
            })
            t_in = rec + int(0.55 * fps)
            t_len = min(n - int(0.55 * fps), int(2.9 * fps))
            if t_len > 0:
                text_segments.append({
                    "id": _uid(cut["shot"], "textseg"),
                    "material_id": tid,
                    "target_timerange": {"start": _us(t_in, fps),
                                         "duration": _us(t_len, fps)},
                    "render_index": 14000,
                    "visible": True,
                    "clip": {"alpha": 1.0, "scale": {"x": 1.0, "y": 1.0},
                             "transform": {"x": 0.0, "y": -0.72}},
                    "extra_material_refs": [],
                })
        rec += n

    tracks = [{"id": _uid("track", "video"), "type": "video",
               "attribute": 0, "flag": 0, "segments": segments}]
    if text_segments:
        tracks.append({"id": _uid("track", "text"), "type": "text",
                       "attribute": 0, "flag": 0, "segments": text_segments})

    content = {
        "id": draft_id,
        "version": "13.0.0",
        "app_version": "5.9.0",
        "type": "draft_content",
        "fps": float(fps),
        "duration": _us(total_frames, fps),
        "canvas_config": {"width": edl["width"], "height": edl["height"],
                          "ratio": "original"},
        "config": {"adjust_max_index": 1, "audio_mix_mode": "auto",
                   "record_audio_last_index": 1, "video_mute": False},
        "materials": {
            "videos": videos, "texts": texts, "audios": [], "stickers": [],
            "transitions": [], "effects": [], "video_effects": [],
            "canvases": [], "speeds": [], "placeholders": [],
        },
        "tracks": tracks,
        "platform": {"app_source": "cc", "os": "windows"},
    }
    meta = {
        "id": draft_id,
        "draft_name": scene.title,
        "draft_fold_path": os.path.abspath(out_dir),
        "draft_root_path": os.path.abspath(os.path.dirname(out_dir)),
        "draft_timeline_material_size": 0,
        "tm_draft_create": int(time.time() * 1_000_000),
        "tm_draft_modified": int(time.time() * 1_000_000),
        "draft_removable_storage_device": "",
        "draft_materials": [{"type": 0, "value": [
            {"id": v["id"], "type": "video", "file_Path": v["path"],
             "duration": v["duration"], "width": v["width"],
             "height": v["height"]} for v in videos]}],
    }
    with open(os.path.join(out_dir, "draft_content.json"), "w") as fh:
        json.dump(content, fh, indent=1)
    with open(os.path.join(out_dir, "draft_meta_info.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    return content


IMPORT_MD = """# Importing "{title}" into CapCut

This bundle was rendered from scratch by `capcut/make.py` — procedural voxel
geometry, no stock footage, no external assets. Everything below is yours to
recut.

## What's here

| Path | What it is |
|------|------------|
| `the_last_torch_1280x720.mp4` | The finished cut, 1280x720 @ {fps}fps |
| `clips/*.mp4` | Each shot as its own clip — import these to recut |
| `captions.srt` | Caption track, standard SRT |
| `poster.png` | Thumbnail / cover frame |
| `shotlist.md` | Shot list with timecodes and camera notes |
| `the_last_torch.edl` | CMX3600 edit decision list |
| `capcut_draft/` | Generated CapCut draft folder (best-effort, see below) |

## Route 1 — clips + SRT (works everywhere, recommended)

1. Open CapCut, **New project**, set the canvas to 16:9.
2. Drag every file from `clips/` onto the timeline, in filename order
   (`01_` through `05_`). Filenames sort into story order on purpose.
3. **Text > Import captions > Local file**, choose `captions.srt`.
4. Add your transitions between shots: the cut was designed for ~0.5s
   dissolves between shots 1-2, 2-3 and 3-4.

## Route 2 — the generated draft folder

Copy `capcut_draft/` into CapCut's draft directory and reopen CapCut:

- Windows: `%LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft\\`
- macOS: `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/`

Rename the copied folder to whatever you want the project called, then fix
the media paths inside `draft_content.json` if you moved the clips.

**Caveat, stated plainly:** CapCut's draft schema is proprietary,
undocumented and changes between releases. This draft was generated without
a CapCut install to test against, so it may need adjusting or may not load
at all on your version. Route 1 is the one that always works.

## Where CapCut's AI actually helps here

The renderer produces clean, silent, evenly-lit footage, which is the
easiest possible input for these:

- **Auto captions** — or just import the SRT above, already timed.
- **Text to speech** — narrate the four captions as VO over the cut.
- **AI background music / auto beat sync** — the shots are cut long on
  purpose so you can retime them to a track.
- **Video upscale / frame interpolation** — the master is {fps}fps at 720p;
  interpolating to 60fps smooths the orbit in shot 3 noticeably.
- **Auto reframe** — for a 9:16 vertical cut, shot 3 (the orbit) and shot 4
  (the push-in) reframe best; the wide reveal in shot 1 does not.

## Re-rendering with changes

Edit `capcut/scene.json` — camera keyframes, shot durations, lighting
presets, captions — then:

```
python3 capcut/make.py all
```

Only changed frames re-render; delete `capcut/out/raw/<shot>/` to force one
shot. Change `"seed"` to generate an entirely different valley.
"""


def build_package(scene, out_dir):
    edl_path = os.path.join(out_dir, "edl.json")
    if not os.path.exists(edl_path):
        raise SystemExit("run `make.py edit` first: %s missing" % edl_path)
    edl = json.load(open(edl_path))
    pkg = os.path.join(out_dir, "capcut_package")
    clips_src = os.path.join(out_dir, "clips")
    os.makedirs(pkg, exist_ok=True)

    clips_dst = os.path.join(pkg, "clips")
    if os.path.isdir(clips_src):
        if os.path.isdir(clips_dst):
            shutil.rmtree(clips_dst)
        shutil.copytree(clips_src, clips_dst)
    for name in ("the_last_torch_1280x720.mp4", "captions.srt", "poster.png"):
        src = os.path.join(out_dir, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(pkg, name))

    write_edl(scene, edl, os.path.join(pkg, "the_last_torch.edl"))
    write_shotlist(scene, edl, os.path.join(pkg, "shotlist.md"))
    build_draft(scene, edl, clips_dst, os.path.join(pkg, "capcut_draft"))
    with open(os.path.join(pkg, "IMPORT.md"), "w") as fh:
        fh.write(IMPORT_MD.format(title=scene.title, fps=edl["fps"]))
    print("package -> %s" % pkg)
    return pkg
