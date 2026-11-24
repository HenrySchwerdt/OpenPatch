> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../DISCLAIMER.md`). Bench sample, water only, never worn.

# ORDER: JLCPCB 6-layer + PCBA for the CUP board (5 boards, all parts JLC-stocked, no consignment)

**Nothing was ordered. No blocker left in the design (2026-11-24); the checks below are done on the JLC quote page before paying.**

1. Fully routed, DRC 0 errors and 0 unconnected on both variants (`ROUTING-GUIDE.md`).
2. **Every BOM line is in JLC stock** (live check 2026-11-24, `jlc_stock_2026-11-24.json`). The motor driver is now **2 x DRV8838DSGR (C86667, U7A / U7B)** instead of the DRV8835 (stock 0); same PHASE/ENABLE logic (`../INTERLOCK.md` I.6b). Low stock: STM32C011F4U6 35, HJ-840 85: order 2-3 spares of each.

**Two packages, one layout** (`variants.py`): `jlc/` = CLEAN (no interlock test pads), `jlc-dev/` = DEV (six bare 0.6 mm interlock test pads TPD1-TPD6 on the underside, `variants/TESTPOINTS.md`). Order one of them; the parts, BOM and CPL are the same.

Files (all generated, `../tools/export_cup_jlc.py`, same set in `jlc-dev/`): `jlc/openpatch-cup-gerbers.zip` (Gerber X2 + Excellon, 6 copper layers, mask, paste, silk, edge), `jlc/BOM-jlcpcb.csv` (34 lines, 56 placements, LCSC numbers), `jlc/CPL-jlcpcb.csv` (rotation = KiCad rotation minus the offset between our footprint and the official LCSC footprint, `jlc_rot_offsets.json`), `jlc/NOT-ASSEMBLED.csv` (bare pads, wire pads, DNP match capacitors).

## PCB options (JLCPCB quote page)

| Option | Value |
|---|---|
| Layers / thickness | **6 layers, 0.8 mm** (the stack-up of the KiCad file: F, In1 GND, In2, In3, In4, B) |
| Size / qty | 38.8 x 25.2 mm bounding box (irregular outline: USB-C notch, hall finger, west tab), 5 pcs |
| Finish | **ENIG** (0.65 x 0.9 mm LGA module, 0.5 mm pitch USB-C, 0.4 mm DFN-6 pads, bare 0.6 mm test pads) |
| Copper | 1 oz outer / 0.5 oz inner |
| Min track / space / via | 0.10 / 0.10 mm; vias 0.30 / 0.15 mm (most), 0.35 / 0.15, 0.40 / 0.20 (JLC 6-layer minimum 0.09 / 0.09, via 0.25 / 0.15: check that the quote page does not add a fee for 0.15 mm drills) |
| Via in pad | **yes, epoxy filled and capped (POFV)**: 71 vias sit in SMD pads (HJ-840 LGA fan-out, U36 pin 2); JLC includes this on 6-layer boards, select it if the page asks |
| Edge | copper to edge 0.2 mm, 0.3 mm keep-out band in the router |
| Holes | 2 x NPTH 1.4 mm (screws), 2 x NPTH 0.6 mm (USB-C pegs), 4 oval plated slots 0.5 x 1.65 mm (USB-C shield tabs) |
| Impedance control | none (USB 2.0 full speed, short) |

## Assembly options

* **Both sides assembled**: bottom side has the sounder FUET-4020 (2.0 mm), the dock hall DRV5032 (0.4 mm), 0402 parts and a few 0603 parts. Standard PCBA, not economic.
* **21 extended lines**, 14 basic lines (`COST.md`). **Low stock: HJ-840 91, STM32C011F4U6 37**; order 5 + 2 spare if the quote allows.
* Not assembled (hand work): cell wires (2), motor wires (4), the rear flex strip with the TMAG5273 (separate order), SWD jig contacts (bare pads), the DNP antenna match capacitors PI1 / PI3 (0 ohm PI2 fitted).

## Checks before paying (JLC 3D preview / DFM)

1. **Pin 1 / polarity of every IC, the LED, the diode and the sounder** in the 3D preview. CPL rotations were derived from pad geometry (our footprint vs the official LCSC footprint): HJ-840, USB-C, STM32, SOT-23-x, SC-70-5, DFN-6, VSSOP-8, WSON-12, X2SON. **Bottom-side parts are the usual trap** (BZ1, U4A DRV5032, C19, RDK, RI1 and others): KiCad reports the bottom rotation in the board frame and JLC mirrors it; check at least U4A, BZ1 and the two drivers U7A / U7B (pin 1 = VM) in the preview and flip the CPL rotation by 180 degrees if they are wrong.
2. **USB-C** TYPE-C-31-M-14: the connector sits in a 9.4 x 6.7 mm notch; the body must be placed from the top with the pads facing the board (a "sink-board" part). Check the 3D preview: the shell tabs go into the 4 plated slots, the two peg holes d0.6 take the plastic pegs.
3. **HJ-840** antenna: the keep-out (x 42.0-43.3, all layers) is the previous estimate; the module manual has no antenna dimensions. The sounder and its pads sit 2.6 mm from the antenna end: **bench RSSI test** (`PIN-CHECK.md`).
4. **Gerber check**: open the zip in a Gerber viewer: USB notch, tab with the screw hole at the west edge, SW1 near the north edge, no copper in the antenna area.
5. **Mechanics requests that the board depends on** (`REVIEW-FIXES.md`): button actuator, flex window and nub x 30.0 -> 33.0 mm; USB receptacle keep-out y 26.35-33.7 (already in the CAD); brass or A2 lid screw near the antenna; 0.1 mm roof relief under the dock hall.
6. Pin check table and the BOM list: `PIN-CHECK.md`.

## Bring-up after delivery (water only)

1. Power from a bench supply on the cell pads at **3.0, 3.4 and 4.2 V**: `3V3` (REG0 output), `VMOT`, `MOT_ALLOW`, TPS2553 EN, boost start; measure on the bare test pads TP1-TP14 and J10-J14.
2. The nRF52840 REG0 output is only 3.3 V when UICR `REGOUT0` is set: flash in normal-voltage mode first (3.3 V on VDDH and VDD, `INTERLOCK.md` I.8); keep the radio at +4 dBm or lower (25 mA external load limit).
3. Supervisor: first flash over the bootloader (USART on pins 14 / 15, BOOT0 pin 17), then clear `nBOOT_SEL`.
4. Hall: measure B at the pre-slide and undocked positions; below 3x margin use the AJ variant (`INTERLOCK.md` I.8).
