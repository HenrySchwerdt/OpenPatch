> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

# Cart pump main board, variant B (57.0 x 10.6 x 0.8 mm, 6 layers), routed 2026-11-25

> **Variant B is PARKED (owner 2026-11-27): do not order this board.** It stays as the template for the variant A board (same chip set,
> interlock and scripts); the A board lives in `a/`.

The cup board's chip set and interlock (`../INTERLOCK.md`) on the long, narrow outline of the cart pump B (`../../../mechanical/V010-CART.md`):
HJ-840 nRF52840 SiP, STM32C011 supervisor, TPL5010 + latch + AND / XOR gates (motor only with MCU enable AND watchdog latch AND supervisor
permit AND adapter-lock XOR direction), TPS2553 load switch, TPS61023 boost, 2 x DRV8838, MCP73832 charger, USB-C, RGB LED, sounder, side button.
Variant A has its own 20.5 x 28.9 board (mechanics 2026-11-25): **not routed yet**.

## State
| Item | Value |
|---|---|
| Board | `cart.kicad_pcb` (routed master), `variants/cart_clean.kicad_pcb` (order this), `variants/cart_dev.kicad_pcb` (+ 6 bare interlock test pads on the underside, `variants/TESTPOINTS.md`) |
| DRC (KiCad 10) | **0 errors, 0 unconnected** on master, CLEAN and DEV; warnings: silkscreen only (overlap / over copper / edge, 2 x 0.5 mm text) |
| Netlist check | `kpy check_board_netlist.py cart.kicad_pcb`: every pad net equals `netlist_cart.json` (78 parts) |
| Stack | 6 layers, 0.8 mm, FR-4 TG155, ENIG; In1 = GND plane, GND pours on all layers; 168 vias 0.40 / 0.20, filled and capped where they sit in a pad (HJ-840 ring >= 1, USB D- pads, I2C_SCL on C6) |
| Rules | track / space 0.10 / 0.10; cell -> boost -> load switch -> drivers 0.30 (pre-order review M5); motor phases 0.20; copper to edge 0.20 (0.30 router band) |
| Parts | 58 assembled (both sides), 34 BOM lines (21 extended), 20 bare pads not assembled; cost and live stock: `COST.md` |
| JLC package | `jlc/` (CLEAN) and `jlc-dev/` (DEV): gerbers + drill zip, `BOM-jlcpcb.csv`, `CPL-jlcpcb.csv`, `NOT-ASSEMBLED.csv`, `CPL-CHECK.md` (rotation table per part), `CPL-VERIFY.md` (independent pad-by-pad check of every CPL row, 58 / 58 OK) |

## Floorplan (board frame: x west -> east, y from the north edge = USB-C wall)
| x (mm) | Top | Bottom |
|---|---|---|
| 0-4.5 | motor pads MP1-4 (0.7 x 1.6, 1.35 pitch), cell pads SP1 / SP2 (own column, 1.0 mm gaps, large + / -) | TMAG strip TL1-4 + adapter-lock pigtail LK1-3 (3V3, GND, DOCK_N), I2C pull-ups |
| 4.5-17 | cell P-FET Q1, boost L1 / U8 / CB1 + FB divider, load switch U20, drivers U7A / U7B, C21, C5 | driver / boost bypass caps, final AND U34, R90, VMOT sense divider (all <= 1.2 mm: variant B motor below) |
| 17-35 | supervisor U30, TPL5010 U5, latch U6, AND U32, XOR U33, AND3 U36, supervisor SWD pads TPS1-3, LED, charger U3 | pull resistors, side switch SW1 (x 31.0, north edge), sounder BZ1 2.5 mm (cell below: 3 mm allowed east of x 28.2), sounder FET / resistor |
| 35-47 | USB-C in its notch (H4 notch geometry, mouth 0.9 mm north of the edge = housing wall), CC resistors, VBUS cap | ESD UU1, nRF SWD pogo pads TPR1-4 (1.27 pitch, x 34.4-38.2) |
| 47-57 | HJ-840, row A (antenna) at the east end; only row A lies in the 3 mm antenna keep-out (no copper except the A1 GND stub and the A7-A8 bridge) | **empty** under the module (HJ-840 manual) and in the antenna zone |

Mechanics changes made for the board (2026-11-25, `mechanical/params.json`, cart_check PASS A + B): side button moved from board x 51.5 to
31.0 (it sat under the HJ-840); interface JSON gained `layers` and the B bottom height zones.

## Rebuild (KiCad 10, Freerouting 2.2.4 jar not committed: set FREEROUTING_JAR)
```
python3 netlist_cart.py                       # snapshot of the cup netlist (pre-order fixes) minus U4A / C80, + LK1-3, cart pin assignment
kpy place_cart.py                             # hand placement + rule check -> placement.json
kpy pinassign_cart.py && python3 netlist_cart.py
OP_LAYERS=6 OP_NAME=cart_try6 kpy build_cart.py   # placed board (6 L, via-in-pad fan-out)
OP_BOARD=cart_try6.kicad_pcb ./flow_cart.sh 60     # headless Freerouting (optimizer / analytics off)
./finish_cart.sh cart_try6.kicad_pcb cart_try6_placed.kicad_pcb cart_f8.kicad_pcb 8   # A* + rip-up + GND pours + DRC
```
Then, as done for the committed board: I2C_SCL had no escape at H5 (west row next to the USB-C shield slot) -> moved to the free inner pad
C6 (P0.13, filled via in pad, `pinassign_cart.OVERRIDE`) and routed by `finish_route.py`; `kpy dedup_vias.py` (3 duplicate same-net vias);
`kpy zone_fix.py board C70:2` (starved thermal); `kpy variants_cart.py cart.kicad_pcb variants`; `kpy gen_cart_rot_offsets.py`;
`python3 export_cart_jlc.py variants/cart_clean.kicad_pcb jlc` (and `cart_dev` -> `jlc-dev`); `kpy verify_cpl.py variants/cart_clean.kicad_pcb jlc`.
Freerouting results are not bit-reproducible between runs; the committed board is the result, the scripts are the method.
Why 6 layers: on 4 layers every module net has to pass the strip south of the USB-C (4.4 mm wide, one inner signal layer) and Freerouting
plus the rip-up router stalled at 29 open connections (4-layer PCB would be 22.79 instead of 77.85 EUR for 5, `COST.md`).

## CPL rotation (JLC) - important for the order
`export_cart_jlc.py`: top = KiCad - delta, **bottom = 180 - KiCad - delta** (delta = LCSC footprint vs ours, `jlc_rot_offsets.json`).
This differs from the cup export (pre-order review H3: bottom = KiCad + delta), which is only right for KiCad rotations of 90 / 270.
`verify_cpl.py` places the official LCSC footprint at each CPL row (bottom = mirrored as seen from the top) and compares every pad: with the
H3 rule BZ1, QBA, U34 and SW1 come out turned by 180 degrees (1.3-3.1 mm off); with this rule all 58 rows fit (worst 0.425 mm = BZ1 land
pattern). The same rule is in Bouni/kicad-jlcpcb-tools (`fabrication.py`: bottom = (180 - orientation) + correction). Still check in the JLC
3D preview: JU1 (origin moved 5.08 mm, review H1), U1, SW1 (actuator toward the north edge), BZ1 (+ pin), QBA, U34, UU1, both drivers.

## HJ-840 pin assignment (`pin_assign.json`, firmware `firmware-rs/openpatch-bench/src/board/cart_v1.rs`, feature `board-cart-v1`)
| HJ-840 pad | nRF pin | Net | Use |
|---|---|---|---|
| D7  | P1.13 | `APHASE`   | out: U7A DRV8838 PH, also supervisor input (PA) |
| G4  | P1.09 | `BPHASE`   | out: U7B DRV8838 PH, also supervisor input |
| C7  | P1.11 | `AENBL`    | out: bridge A enable, 100 k pull-down: 1 = driven, 0 = brake |
| G7  | P0.26 | `BENBL`    | out: bridge B enable |
| G8  | P0.06 | `CHG_STAT` | in: MCP73832 STAT, low = charging (high / high-Z otherwise: use `USBDETECTED` for the cable) |
| F4  | P0.07 | `OC_OK`    | in: TPS2553 FAULT, low = current limit active (100 k pull-up) |
| C8  | P1.12 | `LATCH_Q`  | in: interlock latch readback (RB6) |
| D8  | P0.31 | `DOCK_N`   | in: adapter-lock hall DRV5032FA (pigtail), LOW = adapter locked |
| E7  | P0.28 | `SUP_OK`   | in: supervisor healthy |
| B1  | P0.22 | `LED_R`    | out, active low (RGB common anode on VBAT, 1 k) |
| D1  | P0.19 | `LED_G`    | out, active low |
| D2  | P1.00 | `LED_B`    | out, active low |
| G5  | P0.05 | `SUP_TXD`  | in: UART RX from the supervisor |
| F5  | P0.27 | `SUP_RXD`  | out: UART TX to the supervisor |
| E2  | P0.15 | `SUP_BOOT0` | out: supervisor BOOT0 strap (100 k pull-down) |
| G3  | P0.12 | `SUP_NRST` | io, OPEN DRAIN ONLY (never push-pull high): pulls the supervisor NRST low |
| F8  | P0.29 | `MOT_FWD`  | out: forward intent, HIGH = forward (pull-up: reset default = forward = blocked when undocked) |
| C1  | P0.25 | `BTN_N`    | in: side button, internal pull-up |
| C6  | P0.13 | `I2C_SCL`  | TWIM: TMAG5273 (rear strip), 4.7 k pull-ups, 100 kHz |
| F3  | P0.11 | `I2C_SDA`  | TWIM |
| F7  | P0.30 | `ARM_CLK`  | out: rising edge sets the latch and arms the supervisor, 100 k pull-down |
| E8  | P0.03 | `MCU_EN`   | out: hardware leg of the motor enable (3-input AND `LATCH_Q` & `SUP_PERMIT` & `MCU_EN`), 100 k pull-down |
| B8  | P1.14 | `BUZ_A`    | out: sounder NFET gate |
| E1  | P0.18 | `NRST`     | reset (UICR PSELRESET), TPL5010 RSTn |
| H7  | P0.04 | `VMOT_SENSE` | SAADC AIN2: motor supply after the load switch, 100 k / 100 k (x 2) |
| F1/G1/F2 | D+ / D- / VBUS | `USB_DP` / `USB_DM` / `VBUS_P` | USB (DFU, charging); `USBDETECTED` = cable |
| C2/C3 | SWDIO / SWCLK | bare pads | one-time bootloader flash |
| H2 | VDDH | `VBAT` | the cell: battery voltage through the SAADC `VDDHDIV5` channel (no pin) |

`cart_v1.rs` is generated (`sync_firmware_pins_cart.py`) from the cup board file and this assignment; `board-cart-v1` implies
`board-cup-v4`, so the cup application runs unchanged with the cart pins (`cargo build --release --no-default-features --features
board-cart-v1,angle-tmag,<drive preset>` builds). `DOCK_N` on the cart = adapter-lock hall on the pigtail, low = locked; open pigtail = not locked.

## Open before ordering
1. Same as the cup board (`../cup/ORDER.md`): verify the unverified land patterns (HJ-840 pad size review M6, USB-C, SW1, LED, sounder) and
   check the JLC 3D preview (list above). Bench rules unchanged (cell PCM check, solder the cell last).
2. Small boards for the same order: TMAG5273 strip (4 pads TL1-4) and the adapter-lock hall strip (DRV5032FA + 100 nF, 3 pads LK1-3).
3. Mechanics: board dummy fit with the real USB-C (mouth 0.9 mm north of the board edge, front shield slots 0.29 mm from the edge).
4. Variant A board (20.5 x 28.9) not routed.
