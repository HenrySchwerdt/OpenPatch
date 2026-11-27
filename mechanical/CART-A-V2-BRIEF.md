> TEST ONLY - NOT FOR HUMAN USE (see ../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

# Cart pump A, v2: design brief (2026-11-27; owner go for the package study the same day)

v1 (the current `op_cart.py` A: 70.86 x 49 x 19 box, cap lid, 1 mm pins and fins, head on two screws in thin bosses) is rejected by the
owner: too big, not clean, fragile inside. v2 starts from this brief: every part and function is listed here first, then the package,
then the form, then CAD. Nothing goes into CAD that is not on this list; nothing on this list may be left out of a concept drawing.

## 1. Must contain (functions and parts)
| # | Item | Interface / note |
|---|---|---|
| 1 | Cartridge 1.6 ml ISO 13926-1 (OD 10.95, 43 long, stopper 8) | inserted through the head bore; water only |
| 2 | Original Insight Adapter & Tubing = front end cap | 49 x 19 face; bayonet, 90 deg clockwise; needle into the septum; tubing leaves the far end |
| 3 | Head (tested lock face, KOPF9) | bore, bayonet, lock pocket, seal groove; stays exactly as tested |
| 4 | Adapter-locked detection | 2 mm steel ball in the head + 2 mm pin + side-actuated detector switch (NO, closed = locked, pull-up = fail-safe); ball at y 37.5, z 7.1 (fixed by the adapter's hook block) |
| 5 | Drive | NFP-608 gearmotor (d6 x 16.1), pinion z12 m0.3, gear z40 with the M2 nut, M2 x 0.4 screw, push stem + pusher on the stopper, anti-rotation, washers; stroke 23.7; thrust >= 1.8x need |
| 6 | Angle sensor | magnet d2 x 1 on the pinion face + TMAG5273 |
| 7 | Main board (592 mm2 today) | STM32C011, HJ-840 radio (antenna end at a board edge, away from water and motor), watchdog, supervisor, 2x DRV8838, boost, charger |
| 8 | User interface | USB-C (charge + data), side button SW1, **RGB LED (needs a window / light pipe)**, **sounder BZ1 (needs a sound port)** |
| 9 | Cell | Ampul 301030 LiPo 31.5 x 10.6 x 3.2 (on hand); connected without soldering (connector or spring contacts) |
| 10 | Hardware interlock | motor only with MCU enable AND watchdog AND supervisor AND (LOCKED XOR reverse); unchanged |

## 2. Requirements
| # | Requirement | Source |
|---|---|---|
| R1 | **Clearly smaller than the Accu-Chek Insight** (84 x 52 x 19, 83 ml, user manual App. A) | owner 2026-11-27 |
| R2 | Looks like a designed product, inside and outside: one clean form, the head flows into the body, few seams, no screws on the top face | owner 2026-11-27 |
| R3 | Head and housing seamless where they meet; the head shape is carried into the body | owner 2026-11-26 |
| R4 | Nothing fragile: no free-standing pins or fins; walls and ribs >= 1.6 (FDM 0.4 nozzle); bosses tied into walls | owner 2026-11-27 |
| R5 | Shake-proof: every part held by geometry when the case is closed (no tape-only, no friction-only) | owner 2026-11-26 |
| R6 | Head held robustly (no screws into thin bosses) | owner 2026-11-27 |
| R7 | **Cartridge chamber closed off** from the motor and the electronics (dirt, water from a leak) | owner 2026-11-27 |
| R8 | Simple drive, as few parts as possible | owner 2026-11-27 |
| R9 | USB-C opening in the connector's own shape (stadium), not a rectangle | owner 2026-11-27 |
| R10 | Stack where it helps: drive low, board above, ports at the surface | owner 2026-11-27 (proposal) |
| R11 | Assembly without a soldering iron (spec 1a) | CLAUDE.md |
| R12 | Printable on the Sovol SV01 Pro; visible faces on the bed or vertical, no supports on visible faces | owner |
| R13 | Cartridge change through the head without opening the case; the case opens for service only | v1 |
| R14 | No text or logo on the housing (the warnings live in the docs; no labelling rule applies to the bench device) | owner 2026-11-27 |

## 3. What physics fixes (honest limits)
- **Face**: the adapter sits flush on the head, so the front is 49 x 19 with the cartridge axis 8.74 above the bottom and 11.46 from the
  near side. This is the largest section of the pump.
- **Length**: cartridge 43 (seat to rear end) + stroke 23.7 + drive behind the cartridge = 70.9 body, **80.4 with the adapter** (Insight 84).
  With one screw in line (no yoke, B drive) the cartridge moves back 4.4 mm: 75.3 body, **84.8 with the adapter = as long as the Insight**.
  The yoke drive is one screw + one plain push stem (not two screws); it buys those 4.4 mm.
- **Motor upright** does not fit: gearmotor 16.1 + gear > the inside height (14.6 at most in a 19 body, less in a slimmer one). Lying beside
  the screw it uses the space behind the cartridge that the stem needs anyway at FULL.
- So the bounding box cannot shrink much below 80 x 49 x 19. **R1 is met by volume**: only the head needs 49 x 19; the body behind it can be
  about 37 x 15.6 (gear 12.6 + walls sets the height, drive + stack set the width): roughly **49 ml vs 83 ml (-40 %)**.

## 4. Architecture for the package study (to confirm with the owner)
- Body slimmer than the head; the body flares into the head over the last ~10 mm (the head is the pump's "face").
- **Cartridge chamber** = a closed tube from the head back to a rear bulkhead; the stem passes the bulkhead through a wiper; the chamber
  vents through the adapter (Insight adapter vent, VERIFY) or a labyrinth.
- **Drive bay** behind and beside the chamber: screw, gear, motor parallel to the screw, magnet + TMAG.
- **Electronics bay** beside the chamber, closed: cell at the bottom, board above it (the antenna, LED and button sit right under the top
  face; a cell above the board would shield the antenna).
- Ports: button + LED window on the top face; USB-C at the rear end face (cable does not stand up) unless the owner wants it on top.
- Seam at the cartridge axis (z 8.74): each half carries half saddles; head captured by a collar in a groove; 4 countersunk M2 from below
  into hex nuts; USB-C stadium opening; sounder port on the bottom.
- Lock switch: on a board tongue or a small switch carrier at the pin line (y 37.5, z 7.1), inside the flare.

## 5. Next steps
1. Owner confirms section 4.
2. Package study in CAD: all parts of section 1 placed, collision-free, with the bays and bulkheads; numbers for L x W x H and volume.
3. Form: loft from the head section to the body section, one seam, details (R9, LED, sounder, label); product renders (Blender) from 3 views.
4. Only then: detailed CAD, check, print files.

## 6. Package study result (2026-11-27, `cart_a_v2/package.py`, report `../out/cart_a_v2/package_report.json`)
- Body section 38 x 16.6 (motor edge 36.4 + wall; gear tip 15.04 + wall) with the head's corner shapes, flaring into the 49 x 19 head from
  x 48 (smoothstep, tangent at both ends), rear end rounded R5. Seam at z 8.74.
- Cartridge chamber: partition y 17.25-18.85 from the rear seal ring (x 27.56-28.56, d11.25 around the barrel) to the head. The barrel's open
  rear end and the stem stay in the drive bay; dirt and water from the head side stay in the chamber.
- Drive (v1 yoke drive, screw lane at y 25.6, motor at y 33.4): screw shortened to end inside rib_f (x 32.0).
- Electronics bay beside the chamber: board 29.2 x 17.0, **pcb z 8.34-9.14 so the mid-mount USB-C sits centred ON the seam** (owner
  2026-11-27: a closed opening below the seam left only 0.2-0.7 mm to the parting line; now each half carries half the stadium, no thin
  bridge, and the opening lies fully on the flat far wall). Tongue to the lock switch, switch on the tongue underside (actuator ~7.7,
  the d2 pin at 7.07 covers it). TMAG5273 on the board top at its rear edge (off-axis to the pinion magnet: no separate strip). Cell above
  the board (y 23.8-34.4, z 11.1-14.3, foam pad), clear of the top head boss. SW1 + plunger (x 46.5) and LED + light pipe (x 39.0) on
  the flat top at y 21.5, beside the cell: 3.6 mm wall between the holes (owner 2026-11-27: the first spacing left 0.1 mm). Sounder on
  the board underside, slots in the floor.
- Chamber rear seal wall follows the cavity section (a plain box poked out through the rounded bottom edge in the first render).
- Head fixing: 2 axial M2 through the head face (hidden under the adapter) into bosses of the bottom half (y 21.46, z 3.24) and the top
  half (z 14.04, moved up 0.8 to clear the cell) + the collar in the groove; rear end by non-flexing hooks. No screw visible on the case.
- Check: all parts fit the cavity with 0.2 clearance at FULL and EMPTY; no collisions (intended contacts excluded).
- **Size (with the rear stop ring, below): 81.4 x 49 x 19 with the adapter; envelope 55.9 ml vs the Insight box 83 ml: -33 %.**
- Renders: `cart_a_v2/renders/v2_hero_front.png`, `v2_hero_rear.png`, `v2_xray.png`, `v2_top.png` (Insight footprint in orange),
  `v2_usb.png` (USB-C on the seam).

## 7. Rear stop + review (2026-11-27)
**Rear stop (owner: the cartridge must not slide back further than intended).** Before, only the pusher (via the stopper) held the
cartridge from behind, so pushing a cartridge in would have pushed its stopper. Now a ring wall closes the chamber behind the barrel
(x 27.56-28.56): the barrel's rear end face (r 4.63-5.48) rests on it, only d8.9 stays open for the pusher (d8.4) and the stem. With the
cartridge on the ring its cap face is 0.3 below the head face, exactly the adapter seat of the tested lock. Cost: everything from the
cartridge forward moves +1.0 (yoke travel unchanged, stem 1.0 longer): 81.4 mm with the adapter, full 1.59 ml kept.

**Mechanical / technical review of the package (what holds, what is open):**
- Force path OK: pusher -> stopper -> barrel -> cap -> adapter cup -> bayonet -> head -> 2 axial M2 + collar -> shells; screw thrust ->
  gear washers -> ribs -> shells. Thrust 33 N vs 18.1 N needed (1.83x, v1 drive unchanged). Stem d2 x 24.5 steel: Euler ~2.6 kN.
- M2 x 0.4 screw is self-locking: pressure cannot push the stopper back; the rod only moves under power, behind the interlock.
- Insertion: adapter off (unlocked) -> reverse allowed -> rod home -> cartridge in until it sits on the ring -> adapter on, 90 deg ->
  lock switch closes -> forward allowed -> firmware advances to stopper contact -> prime. Consistent with LOCKED XOR reverse.
- Yoke: the thrust line (stem) is 14.2 mm off the screw axis, ~470 N mm tilting moment at stall. Long rails are impossible (the yoke
  may be at most 2.4 mm long: free length 26.1 minus the stroke 23.7), so as in v1 the yoke is guided by the nut on the screw and the
  stem, whose pusher runs in the glass (lateral load there ~3-6 N, a little extra friction). Price of the 4.4 mm shorter yoke drive.
- Board sits in the parting plane (pcb z 8.34-9.14 around the seam 8.74): clamped between ledges of both halves; its near edge must
  bear on a ledge step at the partition so the USB-C plug force has a stop (detail CAD).
- **Open: antenna.** The cell lies over the board; the HJ-840 antenna end needs >= 3 mm from the pouch (metal laminate), away from the
  water and the motor: give the board a wing into the flare (about x 54-59, y 36.3-39.8) for the antenna end. Electronics to confirm.
- **Open: no soldering (spec 1a).** Cell with a JST-SH lead to a board connector; motor: pre-wired with a connector or spring contacts
  (also open in v1).
- Tolerance: the stop is rigid; the cartridge length tolerance is taken by the adapter's seal on the cap (as on the Insight). A 0.5
  TPU washer on the ring would need the ring 0.5 further back (yoke gap is only 0.3): not planned.
- Option: a small drain at the front of the chamber floor so leak water leaves instead of standing in the chamber.

## 8. Print parts (2026-11-27, `cart_a_v2/shells.py`, report `../out/cart_a_v2/print/shells_report.json`)
Owner: build the print parts, **no text on the housing**. Changes from the package study for printing:
- **Flat top at 19** (the head height): the top half prints roof-down without supports; a rising top in the flare would have needed
  supports on the visible face. The flare stays in plan only. Envelope 61.1 ml (-26 % vs the Insight box).
- Body built from three pieces (rear dome loft, exact prism, flare loft): one loft through all stations waved by up to 2 mm.
- Seam at z 8.74 with a lap joint: the bottom half's inner 0.6 of the wall rises 0.8 above the seam into a groove of the top half.
- Inside, all split at the seam into half-saddles: rear bulkhead (cartridge stop ring d8.9, screw thrust face, motor front seat, wire
  notch), chamber partition, 3 cartridge saddles, rib_f (screw front, magnet window), 2 motor saddles, motor rear stop with 45 deg
  gussets, board edge stop. Bottom only: board ledges (part-free edge strips 19.35-20.35 / 35.3-36.3 on the board), board front and
  rear stops, rear catch bars. Top only: board clamp strips, cell pocket + 2 pressing ribs, plunger guide, light pipe guide, rear hooks
  (plates from the roof). Head: lip ring into the KOPF9 rear groove + 2 bosses for the KOPF9 screws (21.46 / 3.24 and 13.24).
- Ports: USB-C stadium on the seam, button d5.6 + plunger (collar under its guide), LED light pipe hole d2.2, 3 sounder slots.
- Check: every part (FULL and EMPTY, incl. the real yoke and pusher) against both halves: no collisions; every part one valid solid.
- Print files (`mechanical/print/cart_A/`, skirt only, no brim, no supports): **ALLES2.gcode** = everything for one assembly test on
  one bed (3 h 31, `cart_a_v2/bed_all.py`, packed into 127 x 112 around the bed centre for short travel, owner): both halves, KOPF9, yoke, pusher, button plunger + printed stand-ins for the board (plate,
  tongue, USB-C, SW1, LED, TMAG, lock switch, 6 print feet in the bottom parts zone), the motor (body, boss, shaft, pinion, magnet),
  the gear, the screw rod, stem, light pipe and lock pin (d2, flat bottom) and 2 M2 nuts (owner: M2 x 0.4 cannot be printed as a thread
  with a 0.4 nozzle, plain d2 rods test the fit). Single plates: **BODEN2** (1 h 06), **DECKEL2** (1 h 24), **KLEIN2** (11 min) +
  **KOPF9**. The profile's default tree supports are switched off: the parts are designed to print without them.
- Bought / cut parts: M2 threaded rod 31.4 (screw, 0.6-32.0), d2 steel rod 26.9 (stem, press fit into yoke and pusher), M2 hex nut
  (in the yoke pocket), gear z40 + pinion z12 (m0.3) + 2 washers, NFP-608 gearmotor, Ampul 301030 cell + 1 mm foam pad, 2 x M2
  countersunk (head, as KOPF9), clear 1.75 filament or d2 acrylic rod 9 mm (light pipe), 2 mm steel ball + 2 mm pin (lock, as v1).
- Assembly: drive (screw with gear + washers, yoke + stem + pusher, motor) into the bottom half's saddles, board onto its ledges, cell
  + foam into the top half's pocket, plunger + light pipe into their guides; hook the top half in at the rear and swing it down; head on
  (lip into its groove), 2 screws through the face; cartridge in through the head, adapter on.

## 9. Board interface for the electronics (2026-11-27, `cart_a_v2/board_interface.py` -> `../out/cart_a_v2/board_A_interface.json`)
Main rect x 32.6-62.8 / y 19.35-36.3 (pcb z 8.34-9.14, centred on the seam) + tongue x 59.0-63.96 / y 34.5-39.96 (lock switch on its
underside) + an optional antenna wing toward the flared far wall (x 52-59, far edge 37.4-43.8). Part-free strips on both faces along the
partition (y 19.35-20.35) and the far edge (y 35.3-36.3, not at the USB-C x 35-45). Heights: top 1.46 (cell above on foam), bottom 6.84
(floor), 2.8 over the bottom head boss. Fixed: USB-C mid-mount at x 40 (front face y 36.8, centre on the seam), SW1 (46.5, 22.05) and
LED (39.0, 22.05) on top, TMAG5273 on top at x 32.8-34.8 / y 32.4-34.4, sounder underside at (57, 26). **No soldering:** the 4-wire
stepper and the cell plug into JST-SH connectors on the BOTTOM face (too tall for the 1.46 mm top zone): motor leads along the floor
through notches (z 1-5.2, y 34-37.5) in the motor saddles, the rear bulkhead and rib_f to the board's rear-far corner; the cell lead
drops past the board's front edge (gap x 62.9-65.2, y 22-34.5). Print files regenerated with the floor notches (the ALLES2 copy on the
SD card from before has the old notches at z 12.5-15.5: irrelevant for the fit test).
