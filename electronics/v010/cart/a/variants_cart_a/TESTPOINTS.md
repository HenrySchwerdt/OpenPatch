# Cart A board DEV variant: underside test pads

Bare 0.6 mm pads on the underside, on existing vias or joined by a short track. Pump coordinates (mm, x = length from the rear, y = width toward the far wall, seen from the top; cartgeom_a.py).
Bench use only, with water (see DISCLAIMER.md). Probe with a sprung pin; do not solder wires to them.

| Pad | Net | What | x | y |
|---|---|---|---|---|
| TPD2 | MOT_ALLOW | interlock output: motor driver enable | 56.47 | 20.22 |
| TPD3 | LATCH_Q | fault latch output | 41.03 | 22.97 |
| TPD4 | SUP_PERMIT | supervisor permit | 47.05 | 23.03 |
| TPD5 | OC_OK | load-switch over-current flag (low = fault) | 41.13 | 21.74 |
| TPD6 | DOCK_N | adapter-lock detector switch SW2 through RLK (low = locked) | 50.99 | 34.23 |

No free via found for: VMOT (no route to a free spot)
