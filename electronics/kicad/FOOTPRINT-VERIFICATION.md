> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md).

# Footprint / pin-map verification (Rev A fab netlist)

The SKiDL netlist used pin NAMES as pin numbers for every IC except the ISP1807. All maps below were re-derived from the
datasheets in `../datasheets/ds/` (git-ignored local copies) and are encoded in `eco_netlist.py` (`PADMAP`).

| Part | Package / footprint | Source | Status |
|---|---|---|---|
| U1 ISP1807-LR | custom `OpenPatch:ISP1807`, LGA-78 | Insight DS R19 + Eagle lib | VERIFIED (see footprints/ISP1807.md) |
| U2 BQ51013BRHLR (replaces BQ51003YFP) | KiCad `Texas_VQFN-RHL-20` (TI RHL0020 land pattern), EP = pad 21 | TI SLUSB62D pin table (RHL column) | pin map VERIFIED; footprint is the KiCad library TI part |
| U3 MCP73832T-2ACI/OT | KiCad `SOT-23-5` | Microchip DS: 1 STAT, 2 VSS, 3 VBAT, 4 VDD, 5 PROG | VERIFIED |
| U12 XC6206P332MR | KiCad `SOT-23` | Torex DS: 1 VSS, 2 VOUT, 3 VIN (differs from many clones!) | VERIFIED for Torex part; clones may differ |
| U4 STSPIN220 | KiCad `QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm` | ST DS11633 Table 6; pin 7 and EP = GND | pin map VERIFIED; EP size not compared with ST Fig. 17 (text not extractable) |
| U5 TPL5010DDCR | KiCad `SOT-23-6` | TI SNAS651A: 1 VDD, 2 GND, 3 DELAY/M_RST, 4 DONE, 5 WAKE, 6 RSTn | VERIFIED |
| U6 SN74AUP1G74DQER | KiCad `X2SON-8_1.4x1mm_P0.35mm` | TI SCES644D: CLK1 D2 Q_N3 GND4 Q5 CLR6 PRE7 VCC8 | pin map VERIFIED; pad orientation of the KiCad part assumed standard CCW |
| U8 TMAG5273A1QDBVR | KiCad `SOT-23-6`, 2.9 x 2.8 x 1.45 mm | TI SLYS045C: 1 SCL, 2 GND, 3 GND(TEST), 4 VCC, 5 INT, 6 SDA | VERIFIED. **Only package offered is SOT-23-6; the mechanical layout assumed 1.6 x 1.6 x 0.5 mm** (see report) |
| U9/U10/U13 DRV5032FADMRR | KiCad `Texas_X2SON-4-1EP_1.1x1.4mm_P0.5mm_EP0.8x0.6mm` | TI DRV5032 datasheet Table 5-1: 1 VCC, 2 GND, 3 NC, 4 OUT, PAD (GND) | VERIFIED |
| D1 TPD1E10B06 | KiCad `D_0402_1005Metric` (real part is X1SON-2 1.0 x 0.6) | TI: 2 pins, bidirectional | pad-compatible approximation; check against DPY land pattern or use clone C2937015 (DFN1006-2) |
| Q2 DMG1013UW | KiCad `SOT-323_SC-70` | Diodes | standard |
| Q4 AO3401A / Q5-Q7 2N7002 | KiCad `SOT-23` (G=1, S=2, D=3) | AOS / generic | standard; check the LCSC 2N7002 pinout on its datasheet |
| SW1 B3U-1000P | KiCad `SW_SPST_B3U-1000P` | Omron | LCSC lists height 1.6 mm (taller than 1.4 mm under-coil limit; placed outside the coil area) |
| J1 TC2030-IDC-NL | KiCad `Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical` | Tag-Connect | standard (library) |
| MP1 FH12-4S-0.5SH | custom `Hirose_FH12-4S-0.5SH_derived` | derived from KiCad FH12-10S (pads 1-4 re-centred, shield tabs moved 1.5 mm inwards) | **PROVISIONAL**: verify against Hirose drawing |
| BT1 battery contact lands | custom 2 x 1.5 x 1.2 mm @ 1.9 mm pitch | mechanical/out/OP-100.layout.json `contacts` | geometry from CAD; contact part not selected |
| LRX1 coil contact lands | custom 2 x 1.5 x 1.2 mm @ 2.4 mm | provisional position (not in layout.json) | **PROVISIONAL** |
| BQ25120A DSBGA-25, BQ51003 DSBGA-28, TPS22916 DSBGA-4 | not used | 0.4 mm pitch WCSP: inner balls need via-in-pad/HDI; BQ25120A stock 4 pcs at JLC | removed (see ECO list in `netlist-fab.json`) |

Datasheet errors found in the SKiDL netlist (all fixed in `eco_netlist.py`): STSPIN220 SENSEA/SENSEB/TOFF unconnected; BQ51003 AD_EN
tied to GND (it is an output; AD must go to GND); TMAG5273 pin 3 must be GND; BQ25120A PMID/ISET/ILIM/IPRETERM/RESET missing
(moot after removing it); ISP1807 VCC range 1.7-3.6 V.
