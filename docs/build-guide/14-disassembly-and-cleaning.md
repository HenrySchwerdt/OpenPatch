# 14. Disassembly and cleaning (water only)

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

After the tests the pod is taken apart, cleaned with water, inspected and either rebuilt or stored. Only **water** ever went through it, so the cleaning is mechanical: there is nothing to decontaminate and **no disinfection step is needed or implied**. Still treat the outlet needle and the cut rod ends as sharps.

## 14.1 Before you open the pod

1. **Unplug USB.** Unplug the motor lead from J5 and the FFC from J4 (open the flip lock first).
2. **Empty the pod before you open it:** deliver the remaining water through the dummy head into a beaker with normal doses (the same way as in 11.2), then take the pod off the head. Whatever water remains runs out when you pull the end cap off the reservoir over a beaker (14.2 step 11). Do not push water through the outlet needle into the sensor area.
3. Note the final state in the report: carriage position, water volume, leaks, anything abnormal. Photograph the open pod before you touch anything.

## 14.2 Disassembly order (reverse of assembly)

| Step | Action | Reusable? | Notes |
|---|---|---|---|
| 1 | Pull the pod off the dummy head | head: yes | straight back |
| 2 | Push the **dock insert** out with a pin from the open end | yes | keep the variant label |
| 3 | Remove the **4 lid screws** (M1.2 x 6), lift the lid straight up | screws yes, lid yes | cut nothing; the gasket may stick |
| 4 | Lift off the **gasket** | **no** (consumable) | |
| 5 | Open the FFC flip lock, remove the cable; remove the **board screw** (M1.2 x 4); lift the **pod sensor board** | board, cable, screw yes | do not bend the board leg |
| 6 | Remove the **needle hub and needle** from the guard tube (tweezers, pull straight) | hub: after 3 to 5 cycles no; needle: only if straight | sharps |
| 7 | Slide the **carriage** off: unscrew the **leadscrew** with the pin vise from the far end through the far bush, carriage and sleeve; collect the **spindle magnet** (keep away from the sensor) | rod yes; carriage yes; nut: if bonded, with the carriage; **magnet: glued, usually yes** | do not pry the magnet off the sensor-side face |
| 8 | Lift out **gear B** with its sleeve | yes | retaining compound: leave glued |
| 9 | Lift the **motor** out of its cradles with the gear A on the shaft; do not pull the lead; keep the plug | yes | do not remove gear A (it is glued) |
| 10 | Lift out the **reservoir sub-assembly**; pull the **plunger** out of the open end | reservoir yes; plunger core yes; **rings: no** (cast rings are consumed, cut rings are consumed) | |
| 11 | Pull the **end cap** off the port (twist slightly, no tools in the port) | cap: yes if the spigot is intact | |
| 12 | Remove the **septum plug** and the **duckbill valve** (tweezers) | septum **no**; duckbill: check it (02.9), yes if it passes | |

## 14.3 Cleaning

1. **Water only.** Rinse every wetted part (reservoir, plunger core, end cap, tubing, needle, duckbill) with tap water, then distilled water. Use a 1 ml syringe to flush the cap channels (d0.7) and the needle.
2. Scrub only with a soft brush or a lint-free wipe. **Do not use solvents on printed resin parts after assembly** (they craze SLA and swell PA12). Isopropanol was only used before assembly (02.2).
3. **Dry** all parts on a clean wipe, then 12 hours open to air. A wet part must not go back into a pod with the sensor board.
4. **Metal parts** (rod, nut, shim, gears, screws): rinse and dry; wipe a trace of silicone oil on the rod and the gear teeth.
5. **Magnets:** wipe dry, keep them away from steel dust and from each other in a labelled bag.
6. **Do not bake or autoclave anything.** PA12 and SLA resin deform; the pod is not sterilisable and does not need to be.
7. The **dummy head and tubing**: rinse; discard the septum plug.

## 14.4 Inspection and parts life (`mechanical/ASSEMBLY.md` B9)

| Part | Decision |
|---|---|
| Motor, sensor board, magnets, FFC, screws, gears, leadscrew, bushes, dock insert, carriage, plunger core, reservoir | reuse if clean and undamaged; measure the reservoir bore again (16.00 to 16.10) |
| Lip seals, gasket, septum plug, silicone parts | **replace every time** |
| Needle hub and needle | replace after 3 to 5 cycles, or at once if bent or blocked |
| Duckbill valve | re-test (02.9) |
| Printed housing | inspect for cracks at the screw bosses and the snap arms; whitening means strain: note it |
| Cannula adapter (dummy head) | replace the septum plug; inspect the latch notches |

Log the number of cycles per part in the report.

## 14.5 Storage

Dry parts in labelled bags, the motor and the pod board in an ESD-safe tray, the magnets apart. The controller board in an ESD bag with its USB and SWD cables unplugged. Keep the water bottle labelled WATER ONLY and keep everything away from medical supplies.

## 14.6 Disposal

Needles and cut metal ends in a sharps container; printed parts, silicone and electronics according to local rules for electronic waste; the NdFeB magnets as electronic waste, not in household waste bins where they can attach to scrap.

Back to the [index](README.md).
