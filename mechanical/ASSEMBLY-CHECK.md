# Assembly-feasibility and DFM check (`check_assembly.py`)

> **TEST PROJECT: NOT A MEDICAL DEVICE. WATER ONLY. Never worn, never filled with insulin or any other drug** (`../DISCLAIMER.md`).

`check.py` verifies the **final assembled state** (no interference, heights, clearances). It cannot tell whether the parts can be **put together** or **made**.
`check_assembly.py` closes that gap for the bench pod. Latest result: `out/bench/assembly-check/REPORT.md` (+ `img/`).

## Run it

```bash
cd mechanical
python3 check_assembly.py                       # OP-100 (the current bench pod): paths, access, DFM, fits -> out/bench/assembly-check/REPORT.md
python3 check_assembly.py --sizes OP-70 OP-100 OP-200
python3 check_assembly.py --only paths|access|dfm|fits
python3 check_assembly.py --step 0.25           # coarser insertion sweep (default 0.1 mm; the full run takes about 10-15 min at 0.1)
python3 check.py --variant bench --assembly     # check.py as usual, then the assembly check (OP-100 unless --sizes is given)
```

Requirements: SolidCraft CLI (`/usr/local/bin/solidcraft-cli` or the macOS path), Python packages `trimesh numpy scipy shapely rtree manifold3d embreex matplotlib`
(`pip install trimesh numpy scipy shapely rtree manifold3d embreex matplotlib`). The first run exports one mesh per CAD body from `out/bench/<size>.sc`
(about 2 min, cached in `out/bench/assembly-check/meshes/`, keyed by the SHA-256 of the `.sc`; not committed). Exit code 1 means at least one **blocking** finding.

## What it checks

| section | method | blocking when |
|---|---|---|
| 1. paths | `assembly_sequence.json` = the build-guide order as data (part, path segments, tool). Each part moves along its path from outside to the CAD position in 0.1 mm steps; boolean-intersection volume (manifold3d) against everything already assembled. Intended engagement (press zone, snap arms, stretched rings, flexible cable) is declared per step and tolerated. For snap arms the overlap extent gives the required deflection and the cantilever strain (checked against `dfm_rules.json` material limits; reproduces the CAD number of `check.py`). A blocked step triggers a search for any straight or lift-and-slide path. Overlaps whose thinnest side is <= 0.15 mm are reported as *marginal*. | a documented step is blocked by a non-marginal overlap |
| 2. access | screwdriver (tip D1.5/2.0, shaft D3, handle D12 beyond 15 mm) along every screw axis incl. a 10 deg tilt cone, minimum tip length that clears; tweezer cone (15 deg half angle) behind every small part; ZIF flip-lock lever box and tweezer approach | the tool cannot reach |
| 3. dfm | order STLs (`out/bench/fab`, CNC STEP converted) against `dfm_rules.json` (JLC3DP SLA / MJF, CNC PP with sources): inward ray casting (wall thickness), outward ray casting (smallest hole/channel/slot, depth/width), section curvature (CNC internal radius) and axial depth (tool reach) | a feature is below the process **hard floor** (cannot be made as drawn) |
| 4. fits | every mating pair listed in `assembly_sequence.json -> fits`: hole and shaft chord measured on the CAD, Monte Carlo with process sigma (two scenarios: tolerances the project assumes, tolerances the vendor quotes), probability fit / too tight / too loose, post-processing flags and a grep of `docs/build-guide` for the matching instruction | the pair fails (>25 %) as printed and the build guide does not cover the post-processing |

## Files

* `check_assembly.py`: the tool (geometry is read generically from the `.sc`, per-body meshes, mech/layout JSON, order STLs; no CAD file is edited).
* `assembly_sequence.json`: sequence, tools, fit list, tested re-orderings (`proposals`), fix hints per step. **Update it when the build order or a part changes**; bodies that are not in any step are listed in the report.
* `dfm_rules.json`: vendor numbers with source URL and retrieval date, material strain limits, tolerance scenarios, fit-class windows, thresholds.
* Outputs in `out/bench/assembly-check/`: `REPORT.md`, `results-<size>.json`, `img/*.png` (collision sections, DFM maps, fit probabilities, tool sections).

## Reading the numbers (limits)

* Vendor values are a snapshot of public web pages (JLC3DP guide updated 2026-11-04, JLCCNC guide 2025-08-20); PCBWay's own CNC numbers were not found, JLCCNC is the stand-in. **Re-read the live pages before ordering.**
* `hole_bias` (printed holes shrink) is an assumption: the vendor only says "holes generally shrink". Calibrate it with the first bore coupon and update `dfm_rules.json`.
* Rigid-body model: no friction or press-in force, flexible parts (silicone, FFC cable, motor lead) are rigid or absent, gears are tip-circle cylinders, threads are not modelled.
* A path that the checker reports blocked can still be possible by hand in a way that is not in `assembly_sequence.json`; then add that path to the sequence and document it in the build guide, because it is part of the procedure.
