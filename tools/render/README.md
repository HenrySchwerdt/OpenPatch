# OpenPatch render pipeline

TEST PROJECT: bench pod, **water only**, never worn on a person or animal. Photoreal renders of the OP pods and the images of the IKEA-style build guide, regenerated from the CAD.

Needs: SolidCraft CLI (`SOLIDCRAFT_CLI`, default `solidcraft-cli` on PATH), Python 3 with Pillow and cairosvg, the Inter font (falls back to DejaVu). Disk: work files about 0.5 GB (git-ignored `tools/render/work/`, `cache/`).

## Source model

`mechanical/out/bench/OP-xx_real.sc` (made by `mechanical/op_models.py`: library motor, 16 T / 20 T gears, thrust sleeve and collar, rod, nut, magnet, needle, duckbill valve placed by the frames of `mechanical/components/catalog.json`). `oprender.build_base()` adds what the CAD does not hold yet: the four M1.2 x 6 lid screws and the M1.2 x 4 board screw, the Hirose FH12 connector and the 10-pin FFC, a water body in the reservoir, **realistic materials** and the studio lighting preset (HDR environment, soft key + rim). The result is cached in `work/base_OP-xx.sc` and rebuilt when the CAD file, `parts_model.py`, `components.py` or `BASE_VERSION` change. **A re-run after a CAD change therefore regenerates everything.**

The CPU ray tracer accepts opaque bodies only, so translucent materials (clear reservoir, silicone, water) are rendered as opaque pale colours; the transparent PNG background is composited onto a studio backdrop with a contact shadow (`studio.py`).

## Commands

```
python3 tools/render/components.py               # extra component models (25 mm rod, turned gears, coin, tube ...) -> cache/
python3 tools/render/render_heroes.py raw        # hero / exploded / section / detail / turntable raw renders (resumable)
python3 tools/render/render_heroes.py compose    # studio composites, labelled exploded view, line-up -> docs/renders/ + manifest.json
python3 tools/render/render_parts.py raw         # 'parts on the table' scenes
python3 tools/render/render_parts.py compose     # parts + tools pages -> docs/build-guide/steps/
python3 tools/render/render_guide.py --jobs 3    # raw renders of every step (+ check / wrong images), resumable (--only A01 B05, --force)
python3 tools/render/compose_guide.py            # step pages, steps.json, booklet.html, booklet.pdf
```

Quality presets are in `oprender.QUALITY` (samples per pixel, path depth, denoise; fixed seed, so results are deterministic). Cost: about 25 s fixed per image plus about 1 s per 240 000 pixel-samples on 4 cores.

## Files

| File | Role |
|---|---|
| `oprender.py` | base scene, shots (visibility, grey context, explode, section cut, extra parts), camera projection, rendering |
| `parts_model.py` | pod-frame placement helpers (also used for loose parts) |
| `components.py` | extra component models built with the component library generators |
| `guide_data.py` | BOM, tools and the step list of the build guide (the single source of the guide) |
| `render_guide.py`, `compose_guide.py` | step images and pages, `steps.json`, booklet |
| `render_heroes.py`, `render_parts.py` | hero set and parts pages |
| `studio.py`, `icons.py` | backdrop, shadow, arrows, badges; tool and action icons |
| `camera_calibration.json` | calibration of the camera model used to place arrows and labels |
