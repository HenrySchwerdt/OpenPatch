> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench sample, never to be worn.

# Board status (2026-11-18) - **NOT READY TO ORDER**

| Item | Result |
|---|---|
| KiCad 10 DRC (`kicad/drc-report.txt/.json`) | **errors: 41 unconnected items + 19 copper-edge-clearance + 3 zone intersections = 63**; warnings: 50 courtyard overlaps, 7 dangling vias |
| Placement-only board (`kicad/route/placed-unrouted.kicad_pcb`) | 0 placement errors, 139 unconnected (all connections open) |
| Routing | Freerouting 2.2.4 (also 2.4.1 crash, 2.5.0): 53 of 212 connections unrouted after 10 passes; best seen 51 after 31 passes, never converges; imported board has 41 open items (about 81 % of connections made incl. GND) |
| Still open nets | 3V3, NRST, DOCK_N, MOT_ALLOW, QI_CHG_N, most Qi front-end nets (AC1, AC2, BOOT, COM, CLAMP, FOD, TS_CTRL, RECT, COIL_A), STSPIN220 control lines, VMOT, VBAT, ARM_CLK, SWDCLK, TMAG_INT |
| Parts not placed | C22 (third Qi 1206 C0G; no room), C41 may be placed but 10 uF 3V3 bulk is tight |

The Gerber/BOM/CPL packages in `jlcpcb/` and `pcbway/` are exports of this **incomplete** board for review only.

## Why it does not route (measured)

1. **Too many parts for the outline.** Footprint area with pad extents alone is about 430 mm2 plus the ISP1807 (64 mm2); usable area is the 17.1 x 29 mm board (454 mm2) minus 4 cutouts/slot, the antenna keep-out (35 mm2), the bottom no-component zone (y < 13.7 mm, tower) and the 0.5 mm height limit over the battery. About 12 parts needed relaxations first (10k series resistors, VMOT divider, hall decoupling were already removed as "lean").
2. **ISP1807 inner pads need via-in-pad on every signal** (datasheet 4.2); the two pad rows nearest the antenna half cannot escape on L1 because the antenna keep-out is copper-free on all layers.
3. **Layout.json positions conflict with real parts**: encoder halls (TMAG5273 only exists as SOT-23-6 2.9 x 2.8 x 1.45 mm, layout assumed 1.6 x 1.6 x 0.5 mm; DRV5032 pads touch the screw slot and magnet notch edges, moved 0.2-0.45 mm), SW1 moved 0.6 mm from the board edge, FPC connector footprint derived/unverified, battery contacts need a 0.75 mm minimum gap (stack gives 0.55 mm).
4. 0.8 mm board thickness (JLC minimum for 4-layer) instead of 0.6 mm.

## What to relax (in order of effect)

1. **Board size / outline**: +4 mm length (OP-100 -> 46 mm) or moving the Qi 1206 caps and SW1 off the board (flex tail) would give about 25 % more area - the single change most likely to let Freerouting finish. Alternatively move the ISP1807 to the bottom side as well (needs a mechanical re-layout).
2. **Drop functions**: second encoder hall (U10/R-less), TMAG5273 ($3, 1.45 mm tall; DRV5032 pair + firmware calibration is enough for Rev A), VBAT divider, TC2030 (use pogo pads only), 3 -> 2 Qi caps.
3. **Parts**: 0402 -> 0201 (JLC Standard can place; saves about 35 % of passive area), SOT-23 FETs -> one dual FET (SOT-363), STSPIN220 -> smaller driver (DRV8837-class WSON-8 3x2 mm... verify), X2SON-8 -> keep.
4. **Route by hand** the Qi front-end (high-current loops RECT/AC) - autorouter results there are not acceptable anyway.
5. Allow HDI (laser microvia) - not recommended for cost (JLC HDI price unverified).

## Reproduce

```
cd electronics/kicad
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$PY gen_footprints.py && $PY build_board.py && $PY route.py prep
java -jar ../tools/freerouting-2.2.4.jar -de route/op100.dsn -do route/op100_224.ses -mp 10   # download jar from github.com/freerouting/freerouting
$PY route.py import && $PY route.py finish
python3 export_fab.py
```
