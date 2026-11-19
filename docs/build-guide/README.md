# OpenPatch OP-100 bench pod: build guide (step by step)

> **WARNING: BENCH TEST ONLY.** OpenPatch is a test project and **not a medical device**. The pod must **never be worn on, attached to, or used on a person or an animal.** **Fill it with water only. Never put insulin or any other drug into it, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md) and [docs/02-safety.md](../02-safety.md).

This guide works like an IKEA or LEGO manual: **one physical action per step**, one large picture, only the parts and the tool of that step, a **green check picture** ("it must look like this") and, where people go wrong, a **red picture** ("not like this"). Arrows show where a part goes. At most three short lines of text per step.

1. Start with [Parts on the table 1](steps/parts-1.webp) and [2](steps/parts-2.webp) and check that you have everything, then look at the [tools](steps/tools.webp).
2. Do the steps in order. Do not go on if the green picture does not match your work.
3. Print the whole guide: [booklet.pdf](booklet.pdf) (or open [booklet.html](booklet.html)). The same steps as data: [steps.json](steps.json) (id, title, image, parts, tools, check, warnings).

Pictures are rendered from the bench CAD (`mechanical/out/bench/OP-100_real.sc`) with the pipeline in [`tools/render/`](../../tools/render/README.md); regenerate them after a CAD change. The long reference chapters (bill of materials with shop links, measurements and go/no-go limits, electronics, water tests, troubleshooting) are kept in [reference-chapters.md](reference-chapters.md) and the numbered chapter files next to it.

## After step G02: commissioning facts (firmware)

Use these when you follow chapters 10 and 11 (they supersede older numbers there):

| Item | Value |
|---|---|
| Drive feature / preset | `drive-nfp-608-26-45-g16-20` (id 0x25, default), 0.003949 U per step (exact rational) |
| Diagnostics commands | GetFaultLog 0x20, RunSelfTest 0x21, ClearDiag 0x22; result code 31 = NoSchedule |
| STSPIN220 run current | 160 mA; thresholds 213 mA (forward occlusion), 253 mA (draw stall) |
| Unplanned reset of an active pod | raises fault 7-74-002: acknowledge it, then resume |
| Prime after a refill | automatic take-up (160 steps, not counted as delivery), wait one minute (1.7 U/min backstop), then 5 prime commands (prime path about 2.21 U, may shrink after the seal and dead-volume study) |
| Draw rate | capped by the fill needle gauge (29G: 841 pps) |

## Steps (48)

### A. Prepare the parts

| Step | Action | Parts | Tools |
|---|---|---|---|
| [1](steps/A01.webp) | Wash the printed SLA parts | 1x P3, 1x P4, 1x P7, 1x P6, 1x C4 | Isopropanol bath |
| [2](steps/A02.webp) | Post-cure under UV | 1x P3, 1x P4, 1x P7, 1x P6 | UV lamp 365/405 nm |
| [3](steps/A03.webp) | Cut off support remnants | 1x P3 | Flush cutters |
| [4](steps/A04.webp) | Drill the lid pilot holes in the bottom shell | 1x P1 | Pin vise + drills |
| [5](steps/A05.webp) | Drill the lid clearance holes | 1x P2 | Pin vise + drills |
| [6](steps/A06.webp) | Measure the reservoir bore | 1x P6 | Digital calipers 0.01 mm |
| [7](steps/A07.webp) | Check the carriage nut pocket | 1x P3, 1x B6 | Digital calipers 0.01 mm |
| [8](steps/A08.webp) | Mark the rod length | 1x B5 | Fine marker, Digital calipers 0.01 mm, Rod cutting jig (printed or drilled block) |
| [9](steps/A09.webp) | Clamp the rod in the pin vise | 1x B5 | Pin vise + drills, Rod cutting jig (printed or drilled block) |
| [10](steps/A10.webp) | Cut the rod with the cut-off wheel | 1x B5 | Cut-off wheel (rotary tool) |
| [11](steps/A11.webp) | Dress and chamfer both rod ends | 1x B5, 1x B6 | Fine file / stone, Loupe or USB microscope |
| [12](steps/A12.webp) | Roll the rod on glass | 1x B5 | Loupe or USB microscope |
| [13](steps/A13.webp) | Skim gear A to 1.4 mm | 1x B2 | Small lathe (or a machinist) |
| [14](steps/A14.webp) | Turn the hub off gear B | 1x B3 | Small lathe (or a machinist) |
| [15](steps/A15.webp) | Check the thrust sleeve and collar | 1x B4, 1x B4c | Digital calipers 0.01 mm |
| [16](steps/A16.webp) | Check the tongue shim | 1x B10 | Digital calipers 0.01 mm, Fine file / stone |
| [17](steps/A17.webp) | Check the magnets with a compass | 1x B8, 1x B9 | Compass |
| [18](steps/A18.webp) | Punch the fill septum | 1x B14, 1x B15 | Biopsy punch 4 mm / 2 mm |
| [19](steps/A19.webp) | Test the duckbill valve | 1x B13, 1x C5 | Syringe 1 ml |
| [20](steps/A20.webp) | Slice the bushes | 2x B7 | Razor blade + mat |
| [21](steps/A21.webp) | Make the needle hub | 1x B12 | Pin vise + drills |
| [22](steps/A22.webp) | Make the seal rings | 2x M1, 1x B15, 1x P11 | Razor blade + mat, Biopsy punch 4 mm / 2 mm |

### B. Build the sub-assemblies

| Step | Action | Parts | Tools |
|---|---|---|---|
| [23](steps/B01.webp) | Seal ring into the front groove | 1x M1, 1x P4 | Non-magnetic tweezers |
| [24](steps/B02.webp) | Seal ring into the rear groove | 1x M1 | Non-magnetic tweezers |
| [25](steps/B03.webp) | Glue the nose on the front face | 1x P5, 1x C2 | Non-magnetic tweezers |
| [26](steps/B04.webp) | Oil the seal lips | 1x C3 | Non-magnetic tweezers |
| [27](steps/B05.webp) | Fit the nut through the top slot | 1x B6 | Non-magnetic tweezers |
| [28](steps/B06.webp) | Align the nut with a spare rod piece | 1x B5, 1x C2 | Non-magnetic tweezers |
| [29](steps/B07.webp) | Unscrew the rod piece | 1x B5 | Non-magnetic tweezers |
| [30](steps/B08.webp) | Press the shim into the carriage pocket | 1x B10, 1x C2 | Non-magnetic tweezers |
| [31](steps/B09.webp) | Press the fill septum into the end cap | 1x B14 | Non-magnetic tweezers |
| [32](steps/B10.webp) | Drop the duckbill valve into the slot | 1x B13 | Non-magnetic tweezers |
| [33](steps/B11.webp) | Press the valve plug into the slot | 1x M3 | Non-magnetic tweezers |
| [34](steps/B12.webp) | Press the end cap onto the reservoir port | 1x P7, 1x P6 | Non-magnetic tweezers |
| [35](steps/B13.webp) | Push the plunger into the reservoir | 1x P4, 1x P6 | Non-magnetic tweezers |

### C. Shell, drive and needle

| Step | Action | Parts | Tools |
|---|---|---|---|
| [36](steps/C01.webp) | Press the dry bush into the shell | 1x B7 | Non-magnetic tweezers |
| [37](steps/C02.webp) | Press the far bush into the shell | 1x B7 | Non-magnetic tweezers |
| [38](steps/C03.webp) | Lower the reservoir into the shell | 1x P6 | - |
| [39](steps/C04.webp) | Slide the sleeve into gear B | 1x B4, 1x B3, 1x C1 | Non-magnetic tweezers |
| [40](steps/C05.webp) | Lay the carriage on the floor rail | 1x P3 | Non-magnetic tweezers |
| [41](steps/C06.webp) | Lay gear B with its sleeve in the gear plane | 1x B3 | Non-magnetic tweezers |
| [42](steps/C07.webp) | Insert the rod from the dock end | 1x B5 | Pin vise + drills |
| [43](steps/C08.webp) | Turn the rod: carriage runs to the rear stop | - | Pin vise + drills |
| [44](steps/C09.webp) | Press the collar onto the rod end | 1x B4c, 1x C1 | Non-magnetic tweezers, Feeler gauges |
| [45](steps/C10.webp) | Glue the spindle magnet on the rod end | 1x B8, 1x C2 | Non-magnetic tweezers |
| [46](steps/C11.webp) | Lay the motor into its three cradles | 1x B1 | Non-magnetic tweezers |
| [47](steps/C12.webp) | Slide gear A onto the D-shaft, dry | 1x B2 | Non-magnetic tweezers |
| [48](steps/C13.webp) | Check the mesh by hand | - | Feeler gauges |

## Licence

Documentation: CC BY-NC-SA 4.0 (see [LICENSE.md](../../LICENSE.md)). Bench self-build for research and education only.
