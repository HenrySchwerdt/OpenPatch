> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench controller board, never to be worn.

# Ordering the bench controller (JLCPCB PCB + assembly)

Package: `fab/jlcpcb/controller/` (Gerber + drill zip, `BOM-jlcpcb.csv`, `CPL-jlcpcb.csv`, `NOT-ASSEMBLED.csv`, renders, STEP). Regenerate with `tools/export_fab.py controller`
after any layout change. The pod sensor board is a separate package (not built yet, see `../../docs/STATUS.md`).

## Board and options

| Option | Value |
|---|---|
| Layers / size | 4 layers, 44 x 62 mm (see `fab/jlcpcb/controller/README`-less listing: the zip contains the exact outline) |
| Thickness | 1.6 mm (1.0 mm is possible if panelised with the pod board, see COST.md) |
| Surface finish | HASL lead-free (no gold fingers, no special finish) |
| Quantity | 5 PCBs, **2 assembled** (economic assembly, top side only) |
| Min via / trace | 0.3 mm drill, 0.15 mm / 0.15 mm (JLC standard) |
| Impedance control | not needed |

## Assembly checklist

1. Upload gerbers zip, then BOM and CPL. All 37 BOM lines have an LCSC number; `NOT-ASSEMBLED.csv` lists the parts left out on purpose (BZ1 buzzer, J3 header, J6 alternative motor connector, R97, R119, test points).
2. **Check every rotation in the JLC 3D viewer** before paying. `export_fab.py` applies the usual JLC offsets (SOT-23 +180, QFN +270, VSSOP +270, LED +180, SOD-123 +180, SMA +180); polarised parts to confirm: U1 (E73, pin 1 and the antenna end at the top edge), U4 STSPIN220 (QFN-16 dot), U5 TPL5010, U6/U9/U10 (VSSOP-8 dot), U7 INA180, U8 LM393 (SOIC-8 dot), U2 XC6206, Q1-Q14, D1/D2/D4/D5 (cathode bar), LD1-LD4, J1/J4/J5 orientation.
3. Extended parts (9 distinct, $3 setup fee each): E73 C2764963, STSPIN220 C2150516, TPL5010 C473912, SN74AUP1G74 C140267, INA180A1 C122228, USB-C C165948, FH12-10S C506791, motor connector C225113, 1 ohm 0603 C174300. STSPIN220 stock was only about 270 on 2026-11-19: check stock before ordering.
4. The antenna end of the E73 sits at the top board edge; do not add a metal enclosure there. Keep-out: no copper on any layer in the top 3.6 mm band, 14 mm wide (rule area `ANT_KEEPOUT`).

## After the boards arrive (before the motor is connected)

1. Visual check of the E73 castellations and the STSPIN220 exposed pad.
2. Power from USB 5 V with the motor and the FFC unplugged: 3V3 (TP2) 3.2 to 3.4 V, VMOT (TP4) must be **0 V** (T1 in `INTERLOCK.md`).
3. Program through the Tag-Connect pads J2 (TC2030-IDC-NL, nRF52840-DK as probe).
4. Run the acceptance tests T1 to T10 in `INTERLOCK.md`, in particular T3 to T5 (dock / direction) **with the motor free on the bench**, and confirm the DIR polarity (R96 default, R97 alternative, firmware `DIR_FORWARD_HIGH`).
5. Measure the TPL5010 interval (TP12 WAKE about 2 s) and the over-current trip (T9).
6. Water only, into containers: never on a person.

## Known open points

* Motor connector: PicoBlade-compatible CJT A1251WR-S-4P-LCP is assumed (clone drawing not retrievable); confirm the plug on the first motor, else fit the DNP JST GH footprint J6 (needs a hand-soldered part: order JST SM04B-GHS-TB separately).
* J3 (2 x 5 SWD header) is not assembled; the Tag-Connect cable is required.
* The first-board checks of the module footprint (`FOOTPRINT-VERIFICATION.md`) are still required.
