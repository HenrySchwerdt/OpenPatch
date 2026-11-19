> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench controller board, never to be worn.

# Controller layout self-review (rev A, 4-layer 44 x 62 mm)

Checks are reproducible with `tools/review.py controller/controller.kicad_pcb` (plus `tools/chk.sh` for DRC and `tools/silkfix.py` for the silkscreen rules).

| Item | Result | Action |
|---|---|---|
| KiCad DRC | 0 errors, 1 intentional warning (J5 / J6 courtyards: the DNP JST GH footprint is superimposed on the PicoBlade one), 0 unconnected, silkscreen rules (overlap, over copper, edge) 0 | |
| Antenna keep-out (14 x 3.6 mm at the module end, rule area on all four copper layers) | no track, via, pad or zone fill inside on any layer | none |
| Unbroken GND plane | In1 is one 2213 mm2 plane plus a single 8.8 mm2 sliver. An earlier routing pass had let the autorouter cut In1 into 7 islands; fixed by island removal and 4 mm GND stitching vias (F, In1, In2, B tied together). F, In2 and B pours also carry GND | none |
| Motor current loop | VMOT bulk C22 / C24 / C23 are 2.3 / 3.5 / 4.6 mm from the STSPIN220 VS pin (snapped next to the pin); the return runs on In1 directly under the F.Cu | none |
| Shunt sensing | R31 / R39 / R47 (3 x 1 ohm in parallel) with the INA180A1 taps on the supply trunk about 1.5 mm (VMOT side) and 3.5 mm (VMOT_RAW side) from the shunt pads: a quasi-Kelvin connection, trace resistance in the sensed path below 1 % of 0.333 ohm | accepted for a bench rig, calibrate with a known load |
| Decoupling distance (cap to IC supply pad) | U5 2.4, U6 2.0, U9 3.6, U10 2.9, U2 4.6 / 5.4, U1 3.6 / 5.6 mm; U7 INA180A1 6.9 mm; **U8 LM393 (C34) 16.6 mm** | open: the LM393 is a slow comparator, but move C34 next to U8 in the next layout pass |
| Silkscreen | reference text hidden where it overlapped; U1, J1, J4, J5, J6, BZ1 outlines moved to the comment layer; 3 test-point labels not printed | none |
| Module footprint | still to be checked against the first physical module (FOOTPRINT-VERIFICATION.md) | first article |
