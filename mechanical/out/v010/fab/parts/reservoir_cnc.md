# reservoir_cnc

> TEST PROJECT: not a medical device. WATER ONLY, never on a person.

| item | value |
|---|---|
| process | CNC (PCBWay / JLCCNC CNC; polypropylene PP-H) |
| material | PP natural |
| colour | natural |
| finish | as machined; bore Ra 0.8 |
| quantity per pod | 2 |
| uploaded to the vendor | yes |
| volume OP-100 / OP-200 (cm3) | 1.21 / 1.73 |

**Tolerances / features:** +-0.1 mm; bore 25.7 x 4.7 +0.05/-0 (corner R2.35 = D4.7 end mill), wall 1.0 (JLCCNC absolute plastic minimum), end wall 2.0, port d2.0 H7 offset 5.95 mm from the bore centre, outer 27.7 x 6.7. Inspection report requested for bore height and port.

**Post-processing:** None. Deburr the rear edge. The deep pocket (OP-200: depth 23 mm = 4.9 x tool) needs a long-reach tool: ask the vendor; OP-100 depth 15 mm is standard.

**Notes:** RE-FROZEN interface (params.json reservoir_frozen_v010, replaces reservoir_frozen of the bench pod): order once per size AFTER the independent DFM review. Water only.

JLC3DP vendor tolerances: SLA +-0.2 mm (holes shrink, +-0.3), MJF +-0.3 mm (holes shrink, +-0.3); the CAD clearances already assume them (dfm_rules.json).
