> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). v0.1.0 integrated pod board, water only.

# ORDER.md - JLCPCB order for the v0.1.0 board (5 PCBs, 2 or 3 assembled)

Files: `fab/jlcpcb/openpatch-v010-gerbers.zip`, `BOM-jlcpcb.csv`, `CPL-jlcpcb.csv`, `NOT-ASSEMBLED.csv`, renders and `openpatch-v010.step`. **Nothing was ordered.** Do the checks below first; prices in `COST.md`.

## PCB options (JLCPCB quote page)

| Option | Value |
|---|---|
| Layers / thickness | **4 layers, 0.8 mm** (JLC04081H-3313, the 4-layer minimum is 0.8 mm) |
| Size / qty | 46.7 x 29.0 mm, 5 pcs |
| Finish | **ENIG** (charge pads are exposed in the lid window and must not be HASL; fine-pitch X2SON/E73 castellations) |
| Copper | 1 oz outer / 0.5 oz inner, solder mask any colour (black recommended for the lid window contrast) |
| Min track / space / via | 0.15 / 0.15 mm, via 0.5 / 0.25 mm drill (JLC standard for 4 layers), no via in pad, no castellated edge on the board itself |
| Impedance control | none |
| Outline | rounded rectangle R2.5, 3 NPTH 1.2 mm; **parametric**: `board/params.json` + `build_board.py` regenerate for a different tail/pod (the mechanical drive redesign must only change the zones and `fixed` placements) |

## Assembly options

* **Both sides assembled** (tall parts on the bottom: E73 2.4 mm, buzzer 3.0 mm, PicoBlade 3.3 mm, TMAG 1.45 mm). Ask the JLC DFM check whether the bottom side with these parts can be the second reflow (R9 of the architecture); if not, the buzzer and PicoBlade can be hand-fitted (no soldering iron needed for the PicoBlade only if JLC fits it: **do not drop it**, rule 1a).
* Economic PCBA is only possible with parts on one side; this board needs **standard PCBA** (two-side).
* Extended parts: 20 distinct lines (`fab/bom_prices.csv`), each with the JLC setup fee. **Stock problems on 2026-11-19: `C356849` E73-2G4M08S1C stock 1** (CX variant `C2764963`, 729 pcs, has an IPEX connector instead of the ceramic antenna: footprint-identical; add a u.FL flex antenna in the tail), **`C2152498` DRV5032AJDMRR stock 0** (X2SON open drain; fallback `C2152496` DRV5032FADMRR, stock 2124, push-pull 3 mT: the DOCK_N pull-up is harmless, but the threshold fires about 4 mm early, PARTS-LOCK 10), `C180412` SN74LV4040APWR stock 271 (enough). Re-check all stock lines before paying.
* DNP (listed in `NOT-ASSEMBLED.csv`): boost block U8 L1 D6 R55 R56 C31 (fit R45 instead = default), R14, R33, R63 (variants and bring-up), test points, charge pads, Tag-Connect pads, battery cell (not a JLC part).

## Checks before paying (JLC 3D preview / DFM)

1. **Pin 1 / polarity** of every IC, diode, LED in the 3D preview (CPL rotation offsets in `tools/export_fab.py` are the bench set plus SOT-353/TSSOP; bottom-side parts are the usual trap: U1, U4A, U4B, U10T, BZ1, J1, SP1, SP2).
2. The two **DRV5032 X2SON** and the E73 footprint (`../bench/footprints`): X2SON land pattern from TI DMR0004B; E73 pad table from the Ebyte datasheet (`../bench/FOOTPRINT-VERIFICATION.md`).
3. **Spring contacts** BWCD-L3.5W2.0H1.0: free height 1.0 mm vs the 1.05 mm cell-to-board gap in the CAD (0 preload): confirm the vendor drawing; choose a 1.5 mm class contact or thin the spacer.
4. PicoBlade A1251WR-S-4P mating direction (toward -x on the bottom) and that the NFP-608 factory plug fits (UNVERIFIED in the bench notes too).
5. Antenna keep-out (x 41 to 46.7, y 1 to 15.5) is copper and component free on both sides in the Gerbers.
6. Cell: 3.0 to 3.2 mm Li-Po with PCM, 15 x 10 mm class, ~40 mAh (AliExpress, **not verified**): buy 3 candidates; contacts at the -x end of the bay.

## Bring-up order (water only, bench supply or cell on the charger; see `../bench/INTERLOCK.md` section H for T1 to T10)

1. Power the board from a 3.7 V bench supply with a 50 mA limit at VBAT: 3V3 present, idle current below 30 uA with the MCU unprogrammed (budget in README).
2. Flash through the Tag-Connect pads, run POST-S/POST-A with a **bench load resistor 2 x 27 ohm instead of the motor** first; then the motor, then the pod mechanics.
3. HW-A (A12) and the over-current test with a 10 ohm across the motor header (about 0.4 A trips).
4. Charge test on the cradle (2 pogo pins, 5 V current limited to 50 mA): `CHG_STAT` states.
