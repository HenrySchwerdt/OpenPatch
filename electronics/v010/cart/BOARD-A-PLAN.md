> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

# Cart pump A main board: plan (2026-11-27, not routed yet)

Variant A (`../../../mechanical/V010-CART.md`, `op_cart.py`, cart_check PASS) has its own board. Same chip set and the same hardware
interlock as the cup board and the routed B board (`README.md`, `../INTERLOCK.md`): motor supply only with MCU enable AND watchdog latch AND
supervisor permit AND (ADAPTER LOCKED XOR DIR_REVERSE). Nothing in the interlock is removed or relaxed. This file fixes the mechanical
interface from the CAD and lists the work, in order. All coordinates are pump coordinates (mm): x = length (0 rear, 70.86 front face of the
head), y = width (0 cartridge side, 49 far side), z = height (0 underside); values from `op_cart.geometry()` on 2026-11-27.

## 1. Interface from the mechanics
| Item | Value | Note |
|---|---|---|
| Outline | 20.5 x 28.9, x 40.0-60.5, y 18.0-46.9, 0.8 thick, PCB z 5.62-6.42 | `cart_board.py` writes the Edge.Cuts; plus the tongue below |
| **Tongue** (new) | x 60.5-62.96, y 34.7-39.7 (5.0 wide) on the east edge | carries the lock detector switch |
| Parts zones | top up to z 7.87 (1.45), bottom down to z 4.42 (1.2) | the cell lies under the board (top z 3.8): 0.6 air |
| Cell | Ampul 301030 crosswise under the board, x 40.5-51.1, y 12.2-43.7, z 0.6-3.8 (floor pocket) | wires to the cell pads, no bottom parts > 1.2 over it |
| Posts / lid pins | part-free pads d1.6 on **both** faces at (52.1, 18.9), (59.5, 18.9), (59.5, 46.0); lid rib pad x 56.5-57.5, y 18.3-19.3 (top) | the board is clamped between floor posts and lid pins (shake-proof) |
| USB-C | on the north edge (y 46.9, wall y 47.8), centre x 49.0, z 6.02; envelope x 44.53-53.47 | same mid-mount part as B (TYPE-C-31-M-14) |
| SW1 (button) | **top face** now, x 55.5, actuator toward the north wall, actuator centre z 7.22 (pcb top + 0.8) | the far edge of the housing is rounded R5 below z 5; was bottom face |
| **Lock detector switch** (new) | on the tongue, top face, actuator toward +x (east), actuator line y 37.2, z 7.07 (pcb top + 0.65); actuator tip x 63.26 when locked, 63.63 free | replaces the lock hall (DRV5032) and the magnet in the adapter |
| Motor | NFP-608 at y 31.2, x 13-29 (gearhead front at the pinion x 28.76): wires to the west edge | short |
| Angle sensor | magnet d2 x 1 on the pinion face x 30.76-31.76; TMAG5273 strip at x 32.26-33.71 | 6-7 mm west of the board: needs its own strip (see open 3) |

## 2. Lock detection (adapter locked), new
A 2 mm steel ball sits in the hollow floor of the head where the adapter's hook block arrives only in the last ~6 deg of the turn; a d1.7
opening keeps it in (cap ~0.47 proud). The block (0.1 above the floor when locked) pushes the ball back ~0.37 mm; a 2 mm pin behind it
pushes the detector switch on the tongue. Switch requirements:
- side-actuated detector switch (lid / card detection type), operating position <= 0.25 mm from free, total travel >= 0.8 mm, low force
  (< 1.5 N: the ball must not hold the adapter back);
- NO contact (closed = locked) wired to the existing DOCK input of the gate, with a pull-up so that an open switch or a broken connection
  reads "not locked" (fail-safe: forward motor blocked);
- debounce in the gate input RC as on the cup board;
- JLC stock: pick a part with stock when routing (candidates: Alps SPVQ / SPVR detector series, Panasonic ESE, generic 3.6 x 3.5 detector
  switches); the pin length (printed or 2 mm rod) is tuned on the bench so the switch is just open with the ball free.
The SKSCLAE010 (button switch) is NOT suitable here: about 0.2 mm travel, it would be crushed by the 0.37 mm push plus tolerances.

## 3. Open points (decide before routing)
1. **Antenna**: the HJ-840 needs its 3 mm part-free, copper-free end at a board edge, away from the cartridge (water absorbs 2.4 GHz) and the
   motor. Candidate: the north-east corner (outer wall), x 57-60.5, y 40-46.9, next to the lid pin pad at (59.5, 46.0); the tongue and the
   button sit close: check the module footprint fits with USB-C at x 49.
2. **4 layers**: the outline is almost square (no 4.4 mm bottleneck like B), so 4 layers should route: the PCB would drop from about 78 to
   about 23 EUR for 5 boards. Try 4 first, 6 only if it fails.
3. **TMAG strip connection without a soldering iron** (spec 1a): B planned wire pads (TL1-4, LK1-3). For A: a JLC-assembled small FPC or a
   rigid strip with a board-to-board / FPC connector, or move the sensor onto the main board (needs the pinion near the west edge: not today).
   LK1-3 are no longer needed (the lock switch is on the board).
4. Cell connection: pads for the cell tabs (B: SP1 / SP2): same question as 3 (no soldering): use a cell with a JST-SH lead and a
   connector, or spring contacts.
5. Board-side keep-outs for the two head screws and the front lid screw: the head bosses at y 21.2 (x 60.86-64.26) and the front lid boss
   (x 60.56-64.16, y 40.2-43.8) are outside the outline; keep 0.3 mm copper clearance to the east edge there.

## 4. Steps
1. `cart_board.py`: write the A outline with the tongue (Edge.Cuts + keep-outs + interface JSON from `op_cart`).
2. Netlist A = B netlist (`netlist_cart.py`) minus LK1-3, plus the detector switch on DOCK (pull-up, RC), SW1 footprint on the top side.
3. Placement (`place_cart.py` adapted for A): antenna corner first, then USB-C / SW1 on the north edge, switch on the tongue, drivers and
   boost near the west edge (motor wires), supervisor / watchdog / gates in the middle.
4. Route 4 layers (Freerouting flow as for B), DRC 0, netlist check, CPL pad-by-pad check (`verify_cpl.py`, bottom-side rotation rule).
5. JLC export, live stock + cost (`cost_cart.py`), STM32C011 / HJ-840 stock shared with the cup order.

## 5. Ordering note (Black Friday 2026)
JLCPCB's Black Friday runs Nov 18 - Dec 2, 2026 (ET): coupons "up to $251 combined" across PCB, PCBA, stencil (per-coupon values, minimums
and stacking are only shown in the logged-in coupon center); TechPowerUp lists $30 off a $100 PCBA order and $30 off a $50 PCB order until
Dec 2. The A board will not be routed, checked and verified by Dec 2 without cutting corners on the interlock review; claim the coupons now
(free) and check their expiry date, do not rush the order.
