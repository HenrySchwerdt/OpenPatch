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
| R14 | "TEST ONLY / WATER ONLY" marked on the housing | DISCLAIMER |

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
- **Size: 80.4 x 49 x 19 with the adapter; envelope 55.3 ml (body 40.7 + head 6.0 + adapter 8.6) vs the Insight box 83 ml: -33 %.**
- Renders: `cart_a_v2/renders/v2_hero_front.png`, `v2_hero_rear.png`, `v2_xray.png`, `v2_top.png` (Insight footprint in orange),
  `v2_usb.png` (USB-C on the seam).
