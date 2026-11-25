# Cart board DEV variant: underside test pads

Bare 0.6 mm pads on the underside, on existing vias or joined by a short track. Board frame (mm, origin top-left of the board outline, y down, seen from the top).
Bench use only, with water (see DISCLAIMER.md). Probe with a sprung pin; do not solder wires to them.

| Pad | Net | What | x | y |
|---|---|---|---|---|
| TPD1 | VMOT | motor supply after the load switch | 4.88 | 3.49 |
| TPD2 | MOT_ALLOW | interlock output: motor driver enable | 15.48 | 6.76 |
| TPD3 | LATCH_Q | fault latch output (own short track) | 17.95 | 8.95 |
| TPD4 | SUP_PERMIT | supervisor permit | 17.85 | 6.70 |
| TPD5 | OC_OK | load-switch over-current flag (low = fault) | 17.61 | 2.51 |
| TPD6 | DOCK_N | adapter-lock hall output via the pigtail (low = locked) | 2.33 | 7.98 |
