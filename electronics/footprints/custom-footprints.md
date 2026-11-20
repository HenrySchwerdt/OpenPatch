# Footprints still to be drawn (`OpenPatch:*`)

All other footprints in the netlist use standard KiCad names (`Capacitor_SMD:C_0402_1005Metric`, `Resistor_SMD:R_0402_1005Metric`, `Inductor_SMD:L_0603_1608Metric`, `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm`, `Package_TO_SOT_SMD:SOT-23[-6]`, `…SOT-323_SC-70`, `Package_SON:X2SON-8_1.4x1mm_P0.35mm`, `Package_SO:TSSOP-8_4.4x3mm_P0.65mm`, `Diode_SMD:D_SOD-523`, `Diode_SMD:D_0402_1005Metric`, `Button_Switch_SMD:SW_SPST_B3U-1000P`, `Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical`, `TestPoint:TestPoint_Pad_D1.0mm`). When importing into KiCad, please check that every name exists in the installed KiCad version (8/9) - library names sometimes change.

| Footprint | Component | Source of the geometry |
|---|---|---|
| `OpenPatch:ISP1807` | U1 | see `ISP1807.md` |
| `OpenPatch:DSBGA-28_BQ51003_YFP` | U2 BQ51003 | TI datasheet, chapter *Mechanical, Packaging* (0.4 mm pitch, NSMD pads) |
| `OpenPatch:DSBGA-25_BQ25120A_YFP` | U3 BQ25120A | TI SLUSBH2 *Package Option Addendum* |
| `OpenPatch:DSBGA-4_TPS22916_YFP` | U7 | TI TPS22916 *Mechanical Data* |
| `OpenPatch:X2SON-4_1.1x1.4_DMR` | U9, U10 DRV5032 | TI DRV5032 *DMR (X2SON-4)* |
| `OpenPatch:Qi_Coil_Pads` | LRX1 | Coil manufacturer / flex design |
| `OpenPatch:Piezo_9x9` | BZ1 | Murata/manufacturer drawing |
| `OpenPatch:Pad_Pair_Battery_1.0x1.5`, `OpenPatch:Pad_Motor_4x` | BT1, MP1 | custom solder pads |
