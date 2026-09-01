# `capcut/` — "THE LAST TORCH"

A Minecraft-style voxel short, generated end to end in this repo: procedural
world, software renderer, edit, encode, and a CapCut import bundle.

No stock footage, no image models, no game client. Every pixel is computed
from `scene.json` and a seed.

## Why it is built this way

The original ask was to drive CapCut's AI from Claude Code. That is not
possible from this environment, and the reasons are worth writing down
rather than papering over:

- CapCut ships as a **GUI application** for Windows, macOS, iOS and Android.
  There is no headless Linux build to install and no CLI to drive.
- CapCut exposes **no public API** for its AI features (auto captions, TTS,
  auto reframe, AI music). They are in-app only.
- This container's network policy **blocks `capcut.com`** outright, so the
  installer could not be fetched even on a supported OS.

So the pipeline does everything that can be automated — idea, world,
camera, render, edit, encode — and hands CapCut a clean, well-labelled
package for the parts that genuinely need the app. `out/capcut_package/IMPORT.md`
says which CapCut AI features are worth running on the result and why.

## Run it

```bash
python3 capcut/make.py all          # render + edit + encode + package
python3 capcut/make.py render       # voxel frames  -> out/raw/
python3 capcut/make.py edit         # cut and type  -> out/frames/
python3 capcut/make.py encode       # ffmpeg        -> out/*.mp4
python3 capcut/make.py package      # CapCut bundle -> out/capcut_package/
```

`render` is the slow stage and is resumable — it skips frames already on
disk, so an interrupted run continues where it stopped. `--force`
re-renders everything. Only `encode` needs ffmpeg; if it is missing, the
edit still completes as a PNG sequence.

## Dependencies

Renderer, editor and packager are **Python 3.8+ stdlib only** — no numpy,
no Pillow, no ffmpeg — per the repo's zero-external-runtime-deps invariant.
PNGs are emitted from `zlib` + `struct` by hand and the 5x7 caption font is
a table in `pipeline/font.py`, so there is no system font dependency either.

`encode` shells out to ffmpeg, which is a build-time tool rather than a
runtime dependency; it uses the system binary if present and otherwise the
one bundled with `imageio-ffmpeg`.

## How the renderer works

Every voxel face is an axis-aligned rectangle. Rather than interpolating a
polygon, the rasteriser projects a face's four corners to get a screen
bounding box, then solves the exact **ray/plane intersection** per pixel.
That gives exact depth and exact texel coordinates for a couple of float
ops, with no perspective-correction machinery.

Shading is **deferred**: the raster pass fills a G-buffer (block id, face,
texel u/v, depth) and one resolve pass lights it, so a pixel that is
overdrawn is never shaded twice. Faces are sorted front-to-back so the
depth test rejects most work early.

The Minecraft read comes from four cheap cues: per-face directional
brightness, a hashed per-texel colour jitter, a darkened outer texel ring
that draws the block grid, and a nearest-neighbour upscale that keeps pixel
edges hard.

| Module | Role |
|--------|------|
| `pipeline/pngio.py` | RGB frame buffer, nearest upscale, hand-rolled PNG writer |
| `pipeline/font.py` | 5x7 bitmap font and text blitting |
| `pipeline/world.py` | fBm terrain, lake, forest, the tower, drifting clouds |
| `pipeline/render.py` | camera, rasteriser, deferred shading, sky and lighting presets |
| `pipeline/shots.py` | shot definitions, eased camera rigs, `scene.json` parsing |
| `pipeline/edit.py` | dissolves, fades, scrims, titles, captions, end card |
| `package.py` | SRT, EDL, shot list and the CapCut draft folder |
| `make.py` | the four-stage CLI |

## Changing the film

Everything creative lives in `scene.json`: shot durations, camera
keyframes, orbit parameters, easing, lighting presets
(`dawn`/`day`/`dusk`/`night`, or a pair to cross-fade a shot through
sunset), captions and transitions. Change `"seed"` for a completely
different valley.

Camera keyframes are authored by eye against a procedural world, so each
shot is clamped out of terrain and foliage at render time
(`World.clear_camera`) — a bad seed lifts the lens instead of burying it.
