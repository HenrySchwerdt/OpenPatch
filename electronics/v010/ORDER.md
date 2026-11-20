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

---

# v4 CUP pod (single board `cup/`): order notes

Files: `cup/fab/` (Gerber zip, `BOM-jlcpcb.csv`, `CPL-jlcpcb.csv`, `NOT-ASSEMBLED.csv`, STEP). **Nothing ordered.**

* PCB: **6 layers, 0.8 mm, ENIG**, outline `cup/cupgeom.py` (L/U shape, 528 mm2), stackup suggested by the user: L1 signal/parts, L2 GND, L3 signal, L4 power, L5 GND, L6 signal/parts. The routed board uses In1 as GND plane and GND pours on the other layers (`board/route_v3.py` flow); a dedicated power plane is not used, `VBAT`, `VMOT` and `3V3` are routed as 0.25 mm tracks. Min track/space 0.12/0.10 mm, via 0.4/0.2 mm, via-in-pad under the ISP1807 inner pads and on GND pads: **ask for filled and capped vias**.
* Assembly: **two sides**, standard PCBA. Consigned: **ISP1807-LR** (not in the JLC library). Bottom side carries the motor socket J1 (about 2.8 mm tall, side_a block only), DRV5032, spring/pad rows and low parts below 1.1 mm.
* Hand-soldered by the builder: the **two cell leads** to the labelled pads SP1 (+) and SP2 (-), 2.0 x 3.0 mm, top side (the Ampul 301030 has flying wires; no strain relief notch yet). The motor plugs into J1 (CJT A1251WR-S-4P-LCP, `C225113`, land pattern approximated: **verify the footprint and the plug pin order against the vendor drawing and the NFP-608 lead before ordering**).
* Not on this board: TMAG5273 + 100 nF on the **REAR flex strip** (`netlist_v4_rear.json`), pressed onto the pads TL1 to TL4 (west edge, bottom).
* Checks before paying: USB-C proxy `TYPE-C-31-M-12` is top-mount (the stack needs a mid-mount receptacle in a board-edge notch); SKRPACE010 pad mapping; SZYY1615RGB-B pad order and common anode; TPS61023 SOT-563 pin order; UFQFPN-20 land pattern and STM32C011 pin map; ISP1807 pads 65 to 78 are removed from the board footprint (mechanical NC pads, antenna half overhangs the edge).
* Bring-up: as above (bench supply 50 mA limit, flash through the SWD pads, load resistor instead of the motor first); the 5 V boost output must read 4.96 V +- 3 % with `MCU_EN` and the latch armed before the motor plug is fitted; undervoltage rule: no motor start below 3.4 V open circuit.

## v4 follow-ups (2026-11-20)

**Button (side push through a flexing wall zone, no hole).** ALPS SKRPACE010 (`C139797`, 4.2 x 3.2 x 1.4 mm, side-actuated tact, stock 140k, USD 0.066; actuator travel and pad map VERIFY against the datasheet). Position on the current board: body centre pod (39.80, 3.00), top side of the side_a block, body z 6.1 to 7.5, actuator facing the -Y long wall: **actuator tip about (x 39.8, y 1.0, z 6.8)** (body front face y 1.4 + about 0.4 actuator protrusion; inner wall face y 0.9, gap about 0.1 mm). The flex zone in the wall: x 38.3 to 41.3, z 6.0 to 7.5 (the wall above z 6.425 is lid only, `OP-100.mech.json` bottom body top = 6.425). Final position follows the final placement; re-read `cup/placement.json` (SW1) and `cupgeom.py`.

**Sounder on the board (replaces the 9 x 9 piezo disc and its spring pads).** Huanen **MLT-5020** (`C94598`, 5 x 5 x **2.0 mm**, SMD magnetic transducer, stock 111k, USD 0.39), about 85 dB at 10 cm at 3 V / 2.7 kHz (vendor figure, **unverified; a 70 dB requirement is met with margin**). 2.0 mm is too tall for the 1.1 mm zone over the cell, so it sits on the **bottom side of the side_b block** (4.2 mm free below the board), sound into the pod volume and through the lid; drive = one NFET leg (`QBA`, gate `BUZ_A`, 100 k pull-down: off by default) + flyback diode D6 across the coil from `VBAT` (about 60 to 90 mA at 2.7 kHz, short beeps only). Alternatives at JLC: 4 x 4 x 2.0 magnetic FUET-4020 `C391027`, KLJ-4020 `C556936`; no small SMD piezo was found in stock. `BUZ_B` pad of the module is freed.

**Extended to basic swaps (report; not applied to the netlist yet).** 43 of 49 lines are extended (USD 3 setup each, about USD 130 per order). Electrically equivalent basic parts exist for the passives: all 0201 resistors and capacitors become 0402 basic parts (`C25741` 100k, `C25744` 10k, `C1525` 100 nF, `C52923` 1 uF, `C23733` 4.7 uF, `C15195` 10 nF, `C11702` 1k, `C25076` 100R, `C25905` 5.1k, `C25900` 4.7k, `C25890` 3.3k, `C25792` 47k, `C26083` 1M), 22 uF 0603 -> 22 uF 0805 `C45783` (basic), 470R -> 1k (LED current 0.7 mA instead of 1.5), 4.7 M -> 1 M (VBAT sense 1.85 uA instead of 0.4, dock hall pull-up +3 uA idle), 5.6 k -> 5.1 k (current limit 0.186 A), 47 uF 0805 -> 22 uF 0805 `C45783` (4 instead of 3 pieces). That removes **about 18 extended lines = about USD 54 per order** (0402 needs about 20 mm2 more placed area; fill is the limit of this board, so this competes with the shrink step). The ICs, FETs (dual 2N7002DW), connectors, TPS61023 and the inductor have no basic equivalent.

**DRV5032AJDMRR (`C2152498`) is out of stock.** (1) Order variant **DRV5032FADMRR `C2152496`** (stock 2124, same X2SON DMR0004B footprint, push-pull, omnipolar 3 mT class): works with the existing circuit (R19 is then redundant), but the threshold differs and the dock hall switches earlier on the bench pod: re-measure with the cup magnet (d1 x 0.5, 0.7 mm) before ordering many boards; (2) **consign DRV5032AJ** (5 to 10 pieces from TI/Mouser/DigiKey, USD 0.4 each) with the PCBA order as the ISP1807 is already consigned; (3) both footprints are identical, so the same boards take either. Decide after the first dock-field measurement.
