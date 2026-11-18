> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench sample; never wear or use on a person.

# JLCPCB order guide - OpenPatch OP-100 Rev A

**Do not order until every blocker in section 4 is closed.** Current status is in `../STATUS.md`.

## 1. Files

| File | Purpose |
|---|---|
| `openpatch-reva-gerbers-jlcpcb.zip` | RS-274X Gerbers (F/B Cu, In1/In2 Cu, masks, paste, silk, Edge.Cuts) + Excellon drill (PTH/NPTH separate) |
| `BOM-jlcpcb.csv` | Comment, Designator, Footprint, LCSC Part # (JLC upload format) |
| `CPL-jlcpcb.csv` | Designator, Mid X, Mid Y, Layer, Rotation (KiCad frame, mm; check rotations in JLC's preview, JLC corrects most) |
| `../NOT-ASSEMBLED.csv` | parts JLC does not place (ISP1807 module, FPC connector, battery/coil contacts, J1 pads, test points) |

## 2. PCB form (quote page)

| Field | Value |
|---|---|
| Base material / layers | FR4, **4 layers** |
| Dimensions | about 17.1 x 29.0 mm (board has notches and one slot; JLC reads Edge.Cuts) |
| Product type | Industrial/Consumer electronics (keep default; Aerospace/Medical adds Kelvin test) |
| Different design in panel | 1 |
| Delivery format | Panel by JLCPCB (assembly Standard needs rails/fiducials; board < 70 mm) |
| PCB thickness | **0.8 mm** (0.6 mm is not selectable for 4 layers; +0.2 mm vs mechanical stack) |
| Impedance control | no |
| Layer sequence | JLC04161H-3313 (default) |
| Outer copper / inner copper | 1 oz / 0.5 oz |
| Surface finish | **ENIG** (1 u"; needed for 0.4 mm pads and via-in-pad) |
| Via covering | **Epoxy filled and capped** |
| Min via hole / diameter | **0.2 mm** (design uses 0.2/0.4 mm vias; the 0.15 mm option costs +$16) |
| Min track/space | 0.1 mm / 0.1 mm used (JLC min 0.09 mm) |
| Board outline tolerance | +/- 0.2 mm (standard); slot 2.8 x 2.8 mm |
| Solder mask / silk | any (design silk text "TEST ONLY - NOT FOR HUMAN USE") |
| Remove order number | specify location or pay the fee |
| Quantity | 5 |

## 3. Assembly form

| Field | Value |
|---|---|
| Assembly | PCB Assembly, **Standard**, assembly side **both** (hall sensors, 0402 passives and FPC pads are on the bottom) |
| PCBA qty | 2 |
| Tooling holes / edge rails | added by JLC (panel) |
| Parts | upload BOM + CPL; ISP1807 (C5264268, stock 0) must be **consigned (customer-supplied) or left off**; FH12 connector, battery/coil contacts: leave off (listed in NOT-ASSEMBLED.csv) |
| Special notes (paste into order remarks) | "TEST/bench build, 2 PCBA. Place U1 only if parts arrive: ISP1807 LGA 8x8, antenna end at board edge, keep-out zone has no copper. U2 (BQ51013B) and U4 (STSPIN220) are QFN with exposed pad. Bottom side: 0402 passives max 0.5 mm height. Confirm rotations of SOT-23-5/-6, X2SON-4/-8 and VQFN-20 in the preview." |
| Confirm parts placement | yes ($0.45) |
| X-ray | automatic for QFN/LGA parts (per-part fee) |

## 4. Pre-order checklist / blockers

- [ ] **Routing complete and DRC clean** (see ../STATUS.md; if not, do not order).
- [ ] Mechanical re-check of the **0.8 mm** PCB (was 0.6 mm), **TMAG5273 SOT-23-6 (2.9 x 2.8 x 1.45 mm)** on the top side at x 26.9 / y 22.6 (layout assumed a 1.6 x 1.6 x 0.5 mm part on the bottom), SW1 1.6 mm, 1206 C0G caps 1.6 mm, FPC connector, dock hall at x 35 / y 14.6 on the bottom.
- [ ] Battery contacts: select a real spring contact that fits 1.5 x 1.2 mm lands at 1.9 mm pitch and a 0.55 mm gap (AVX 709155001610004 does not fit as is, see ../COST.md); same for the 0.5 mm-pitch motor tail and the coil contacts (coil contact positions are provisional).
- [ ] Antenna keep-out is 8.6 mm wide (datasheet recommends 18 mm min): expect reduced BLE range.
- [ ] STSPIN220 current limit (VREF 0.105 V / 1.0 ohm = about 105 mA) vs the actual motor (3 V / 75 mA class), tune R69 and the motor driver current before first run.
- [ ] Qi series capacitor: 3 x 100 nF C0G 1206 (C170182, Extended) - resonance must be tuned with an LCR meter against the real coil.
- [ ] LCSC stock re-check (BQ51013B 813, STSPIN220 285, TMAG5273 3,402, DRV5032 2,254 on 2026-11-18).
- [ ] Open the Gerbers in a viewer (KiCad/gerbv) and compare with `render/` before paying.
- [ ] ISP1807 modules ordered (Digikey) and shipped to JLC / on hand.
