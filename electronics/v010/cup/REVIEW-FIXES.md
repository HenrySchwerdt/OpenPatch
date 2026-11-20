> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Water only, never worn.

# Review fixes applied to the CUP board (2026-11-20, from `review/BOARD-SANITY-REVIEW.md`)

| # | Fix | What was done (files: `cupgeom.py`, `place_cup.py`, `design/netlist_v4.py`) |
|---|---|---|
| 1 | USB-C | proxy top-mount part replaced by the JLC-stocked **laminated (mid-mount) 16P receptacle HRO TYPE-C-31-M-14, LCSC `C223907`** (stock 2143, USD 0.36), footprint `V010:USB_C_Midmount_M14` (**land pattern approximated from the M-12 pad row: VERIFY with the HRO drawing**), board notch x 18.8 to 28.2, y 29.5 to 33.5, receptacle centre x 23.5 on the +Y edge. Height: the board mid-plane (z 5.7) inside the body, bottom about 4.1 (touches the cell top 4.1: VERIFY), top about 7.3 < lid 7.6 |
| 2 | Pocket roof | `LOW_ZONES` = (cell x 9.4 to 40.9: 1.1 mm) and (roof x 35.16 to 47.07, y 6.45 to 17.05: **0.4 mm**); the placer now rejects bottom parts taller than the zone limit, so C50, R21, R91, R92 land on top or elsewhere (C1 was removed in the audit). **U4A (0.4 mm package) touches the roof (0.0 mm): a 0.1 mm roof relief under the hall is requested from the mechanics** (no thinner package exists) |
| 3 | West-end wiring hub | 6 top-side pads 1.0 x 1.8 at 1.25 mm pitch: motor A+ (10.0, 25.0), A- (11.25, 25.0), B+ (12.5, 25.0), B- (10.0, 27.2), cell + (11.25, 27.2), cell - (12.5, 27.2), next to the TL1 to TL4 strip pads (bottom, y 23.8); **1.5 x 2.5 mm wire notch** in the west edge (x 7.8 to 9.3, y 25.3 to 27.8); the SP anchors at x 37 are gone; cell +1.5 mm east and wire channel x 7.5 to 9.4 are mechanics changes (lead end WEST) |
| 4 | Saddle | board west edge x >= 7.8 |
| 5 | Board support | the board must be held by raised ledges at z 5.3 and the pocket roof (mechanics); keep 1.0 mm part-free pads above the ledges and for the lid hold-down ribs: **positions not known yet** (`cupgeom.HOLD_PADS` is empty, to be filled when the mechanics report x/y) |
| 6 | Button | SW1 moved to the **north edge**, centre (30.0, 31.65), actuator toward +Y at x = 30.0 (tip about y 33.7: flex zone in the +Y lid wall, flat part below the R1.8 fillet, z 5.6 to 6.7, requested from the mechanics); the **side_a foot is deleted**: only the hall finger (x 37.9 to 40.9, y 10.4 to 17.15) and the side_b block remain |
| 7 | Sounder | magnetic sounder stray field at the dock hall: dipole estimate for a d2 x 0.5 mm NdFeB-class disc (m about 1.3e-3 A m2): B = 2.5e-10 / d^3 tesla = **0.36 mT at 8.9 mm**, 10 % of a 3.5 mT-class hall threshold (DRV5032FA, datasheet threshold to be checked) and below 10 % beyond about 9 mm. The farthest corner of the only block that holds a 2.0 mm bottom part (side_b, body y <= 22.5 to stay out of the cell) is 8.9 mm from the hall: **BZ1 sits there (37.6, 20.5)**: the margin is about 10 %, **bench-verify** (hall false trigger with the sounder driven) and the **sound level in the sealed shell** (vent/port with membrane if too quiet) |
| 8 | Minor | SWD pads in one row (x 34.0 to 39.2, y 32.6, north edge); heights: 0805 and 1008 parts now 1.25 mm (top side only over the cell), SOT-23-6 1.45; **non-magnetic (A2 or brass) lid screw near the antenna: note for the mechanics** (steel M1.2 screw 2.3 mm from the module corner) |


# Review fixes round 2 (2026-11-20): independent netlist review (coordinator ids C/M/m), SPICE results (F) and the pin check (`PIN-CHECK.md`)

| Id | Fix | Where |
|---|---|---|
| C1 | `R26` = 6.8 k 1 % (C25917): TPL5010 2 s (10 k = 7.6 s) | netlist, INTERLOCK I.8 |
| C2 | `U33` NAND -> **74AUP1G86GW-TP XOR (C48995440, SC-70-5, stock 3001)**, net `DOCK_XOR` = `DOCK_N` XOR `MOT_FWD`: docked + reverse blocked (H15) | netlist, INTERLOCK I.8 truth table |
| C3 | `C70` 4.7 uF 16 V 0603 (C19666) on `3V3` at U1 H3/H4; REG0 25 mA external limit (PS v1.7 p. 84, second-hand) and the 3.0 / 3.4 / 4.2 V bring-up test noted | netlist, INTERLOCK I.8, PIN-CHECK |
| M1 | `U36` -> **3-input AND `EM74AUP1G11GM` (C54929506, DFN-6 1.0 x 1.45, stock 9000)**: `LATCH_Q` AND `SUP_PERMIT` AND `MCU_EN`; `R18` 100 k pull-down on `MCU_EN`. The SC-70-6 74AUP1G11GW (C554956) has stock 3, so the DFN clone is used | netlist, footprint `UFDFN-6_1.45x1.0_P0.5` |
| M4 | bare 0.6 mm test pads on `SUP_NRST`, `SUP_BOOT0` (= SWCLK PA14, pin 17) and `BPHASE` (= SWDIO PA13, pin 16); the pin numbers 18/19 of the review are TSSOP20 numbers. DS13866 guarantees the PA14 internal pull-down at reset, so **R79 is not needed**. nRF drives `SUP_NRST` open drain only (FIRMWARE-PINMAP note) | netlist TP1-TP3 |
| M5 | bare 0.6 mm test pads on `VBAT, VMOT_PRE, VMOT, MOT_ALLOW, LATCH_Q, SUP_PERMIT, OC_OK, DOCK_N, SUP_TXD, SUP_RXD, VBUS_P` (TP4-TP14, zero BOM, top side, outside the antenna keep-out) | netlist, `place_cup.py` (group `tpx`) |
| M6 | capacitor ratings **already satisfied**: C19702 (10 uF 0603) is 10 V (JLC "CL10A106KP8NNNC 10 V") and C45783 (22 uF 0805) is **25 V** (CL21A226MAQNNNE), so CU1, C5, CB1, C21 stay; the old note "6.3 V" was wrong. No part change, no extra extended-part fee | PIN-CHECK |
| m2 | `RI1`, `RI2` 4.7 k pull-ups SDA/SCL (C25900, basic) | netlist |
| m4 | FUET-4020 coil 17 +-3 ohm (< 25 ohm): series `RBZ` 22 ohm 0603 (C23345, basic): 4.2 V / (17 + 22 + 3) = 100 mA peak; flyback D6 across the coil only (nets `PZ_C` / `PZ_A`) | netlist |
| m5 | large +/- and A+ A- B+ B- silkscreen at the cell and motor pads | `build_cup.py` |
| m6 | FIRMWARE-PINMAP (HJ-840 table, H2 = VBAT, HV mode), PART-AUDIT (current part list) and FMEA v4 delta regenerated from the netlist | `tools/gen_cup_docs.py`, FMEA.md |
| F1 (SPICE) | `RDK` 100 k `3V3` -> `DOCK_N` (a floating hall line must read undocked) | netlist |
| F3 (SPICE) | `C71` second 10 uF 10 V on `VBAT` at the TPS61023 input | netlist |
| F4 (SPICE) | INTERLOCK I.5 ILIM range 0.50-0.62 A (0.505 / 0.557 / 0.616) | INTERLOCK I.8 |
| F5 (SPICE) | `RNR` 100 k `SUP_NRST` -> `3V3` (TPL5010 RSTn open drain; the STM32 internal pull-up is not relied on) | netlist |
| F6 (SPICE) | `C61` 100 nF `VMOT` -> GND at the DRV8835 VM pin | netlist |
| not changed | hall stays DRV5032FA; bench note: measure B at pre-slide and undocked, margin < 3x -> DRV5032AJ with 1 M pull-up | INTERLOCK I.8 |

**Pin check fixes (details in `PIN-CHECK.md`):** USB-C footprint/notch replaced by the real HRO sink-board pattern, STM32C011 UFQFPN20 pin map (was TSSOP20 numbering), SKRPACE010 (top push) replaced by SKSCLAE010 side push (button moved x 30.0 -> 33.0, mechanics request), AND gates SOT-23-5, LED and sounder land patterns, no STM32 exposed pad, screw holes (d1.4 NPTH + d2.8 keep-out, `cupgeom.SCREWS`), west board tab for screw W, support-pad and wire-channel keep-outs from `OP-100.mech.json`.
