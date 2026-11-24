# Cup board DEV variant: underside test pads

Bare 0.6 mm pads on the underside, on existing vias or joined by a short track. Board frame (mm, origin top-left of the board outline, y down, seen from the top).
Bench use only, with water (see DISCLAIMER.md). Probe with a sprung pin; do not solder wires to them.

| Pad | Net | What | x | y |
|---|---|---|---|---|
| TPD1 | VMOT | motor supply after the load switch | 8.50 | 4.50 |
| TPD2 | MOT_ALLOW | interlock output: motor driver enable (own short track) | 1.55 | 4.35 |
| TPD3 | LATCH_Q | fault latch output | 32.25 | 12.10 |
| TPD4 | SUP_PERMIT | supervisor permit | 7.65 | 4.15 |
| TPD5 | OC_OK | load-switch over-current flag (low = fault) | 9.20 | 4.60 |
| TPD6 | DOCK_N | dock hall output (low = docked) | 35.53 | 15.18 |
