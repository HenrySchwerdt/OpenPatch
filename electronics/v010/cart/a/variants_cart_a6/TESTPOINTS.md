# Cart A board DEV variant: underside test pads

Bare 0.6 mm pads on the underside, on existing vias or joined by a short track. Pump coordinates (mm, x = length from the rear, y = width toward the far wall, seen from the top; cartgeom_a.py).
Bench use only, with water (see DISCLAIMER.md). Probe with a sprung pin; do not solder wires to them.

| Pad | Net | What | x | y |
|---|---|---|---|---|
| TPD1 | VMOT | motor supply after the load switch (own short track) | 52.95 | 30.21 |
| TPD2 | MOT_ALLOW | interlock output: motor driver enable | 54.87 | 29.66 |
| TPD3 | LATCH_Q | fault latch output | 41.74 | 22.58 |
| TPD4 | SUP_PERMIT | supervisor permit | 46.79 | 22.80 |
| TPD5 | OC_OK | load-switch over-current flag (low = fault) (on its own new via to an inner-layer track) | 43.99 | 26.44 |
| TPD6 | DOCK_N | adapter-lock detector switch SW2 through RLK (low = locked) | 45.01 | 22.72 |
