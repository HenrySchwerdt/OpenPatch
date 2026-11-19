# External parts lock (bought-in parts)

> Test project, not a medical device. Goal: fix every **externally sourced part** early so mechanics, electronics and firmware can be planned around it. Criteria, in order: **easy sourcing** (private buyer, small qty, stable listing) → **precision / published datasheet** → **no soldering / easy assembly** → **price**.
>
> Status: **LOCKED** = chosen and dimensions from a datasheet; **LOCK-AFTER-SAMPLE** = chosen, but must be measured on a bought sample before freezing CAD; **CANDIDATE** = no verified listing yet. Changing a LOCKED part requires a decision entry in `docs/STATUS.md`.

| # | Function | Chosen part | Backup | Source | ~Price | Status | Why / notes |
|---|---|---|---|---|---|---|---|
| 1 | Cannula (site) | Roche **Accu-Chek Insight Flex** cannula head (6/8/10 mm) | — | pharmacy / prescription | consumable | LOCK-AFTER-SAMPLE | Flattest horizontal site connector; dims not public → dock fit-test coupon (`mechanical/out/fab/dock-coupon/`) |
| 2 | Drive motor | **NFP-608-26.45-SGM** (Ø6, 20 steps/rev, 26.45:1, 4.8 V, 26.5 Ω, Ø2 D-shaft, JST 1.25 lead) | Zhaowei ZWBPD006006-6 (6.43:1) | nfpshop.com / precisionminidrives.com | $6.60 (10+: $5.40) | LOCK-AFTER-SAMPLE | Only Ø6 geared stepper orderable in small qty with a full drawing; verify shaft length, D-flat, connector type |
| 3 | Gear pair motor → screw | **GHW-Modellbau module 0.3: 16 T motor gear 390754 (bore 2.0, 16.15 €) : 20 T screw gear 753020 (bore 2.0, hub turned off, 3.10 €)**, ratio 0.8, built centre 5.51 mm | 18 T : 18 T (390755 ×2, 32.30 €, 0.00494 U/step) | ghw-modellbau.de | ~19.25 € | LOCK-AFTER-SAMPLE | Article numbers/prices verified on the GHW page 2026-11-19. 15:12 and 15:15 do not clear the carriage lane (centre ≥ 5.5 mm); **U/step 0.003951 — firmware needs a matching preset (g15-12 and g1-1 are wrong for this pair)**; screw-side gear needs a d2.0/d1.6 sleeve (rod M1.6) |
| 4 | Leadscrew | **M1.6 × 0.35 threaded rod, stainless A2 (DIN 976)**, cut to length | brass | Amazon / AliExpress / Mädler | ~2 € | LOCKED | Standard metric thread, self-locking |
| 5 | Carriage nut | **DIN 934 M1.6 hex nut, brass** (AF 3.2) | stainless | same | <1 € | LOCKED | Pressed into the printed carriage hex pocket |
| 6 | Reservoir | **CNC polypropylene stadium part** (frozen, `mechanical/out/bench/fab/reservoir-cnc/`) | through-bore + plug variant (200 U) | PCBWay CNC | est. 30–60 $ per size | LOCKED (design) | Insulin-compatible material, ordered once per size, qty 2 |
| 7 | Spindle magnet | **Ø2 × 1 mm NdFeB N52, diametrically magnetised** | Ø2 × 2 mm | supermagnete.de / AliExpress | ~0.30 € | CANDIDATE | Verify a diametric 2 × 1 listing; axial will not work for the angle sensor |
| 8 | Dock magnet | **Ø2 × 1 mm NdFeB N52, axially magnetised** | Ø2 × 2 | supermagnete.de | ~0.20 € | LOCKED | Standard item |
| 9 | Angle sensor | **TI TMAG5273** (3D hall, I²C, SOT-23-6) | AS5600L (larger) | LCSC / JLC assembly | ~1.5 $ | LOCKED | Per-revolution delivery verification; register map still to verify in firmware |
| 10 | Dock sensor | **TI DRV5032 (higher-threshold variant)** | TMAG threshold | LCSC | ~0.5 $ | CANDIDATE | Pick the variant so DOCKED asserts only when fully latched |
| 11 | MCU module (bench) | **Ebyte E73-2G4M08S1C (nRF52840)** | Raytac MDBT50Q-1MV2 | LCSC / JLC assembly | ~5–7 $ | LOCK-AFTER-SAMPLE | LCSC-stocked → no consignment; firmware board `bench-e73` |
| 12 | Motor driver | **ST STSPIN220** | TI DRV8834 | LCSC | ~1.5 $ | LOCKED | Low-voltage micro-stepper driver with current limit |
| 13 | Watchdog | **TI TPL5010** (~2 s interval) | — | LCSC | ~0.8 $ | LOCKED | Independent hardware watchdog in the motor interlock |
| 14 | Motor connector (bench) | **Molex PicoBlade 53261-0471** (4-pin 1.25 mm SMD) | JST GH SM04B-GHS-TB (DNP) | LCSC | ~0.3 $ | LOCK-AFTER-SAMPLE | Factory motor lead plugs in, no soldering; confirm PicoBlade vs GH on the first motor |
| 15 | Pod ↔ controller cable | **0.5 mm pitch FFC, same-side contacts** + bottom-contact ZIF connectors | — | LCSC / AliExpress | ~1 $ | CANDIDATE | Pin count from the final pod board |
| 16 | Outlet check valve | **miniature silicone duckbill, OD ≤ 3 mm**, cracking 1–5 kPa | flap valve | Minivalve / Vernay / AliExpress | 1–4 $ | CANDIDATE | No verified listing yet — needed for draw-mode refill and anti-siphon |
| 17 | Outlet needle | **30G blunt dispensing needle 1/4"** (Nordson EFD-type, OD 0.31 mm) | 27G | Nordson EFD resellers / AliExpress | ~0.10 $ | LOCKED | Published dimensions; cut to length |
| 18 | Fill septum | **punched Ø4 × 2 mm from platinum-cure silicone sheet, Shore A 40–50** | GC injection septa | AliExpress / lab suppliers | ~3 $ sheet | CANDIDATE | Medical (USP VI) grade for insulin tests |
| 19 | Plunger seal | **cast platinum-cure silicone, Shore A 40** in the printed mould | PCBWay silicone moulding (group buy) | Smooth-On / Elkem / Wacker | 15–25 € kit | CANDIDATE | Only DIY step; for insulin tests use medical grade |
| 20 | Screws | **M1.2 pan head, stainless (ISO 7045)**, lengths 3/4 mm | — | Amazon / AliExpress | ~3 € set | LOCKED | |
| 21 | Programmer | **Nordic nRF52840-DK** (also usable as dev target) | J-Link EDU Mini / CMSIS-DAP clone | Mouser / Digikey | ~40 € | LOCKED | Firmware already builds for the DK |

## Recommended next action: one "sample order"

Before freezing CAD/PCB, buy **samples of every LOCK-AFTER-SAMPLE and CANDIDATE part** (total roughly 60–100 €): 5× NFP motor, a GHW 15T/12T set, magnets (diametric + axial), DRV5032 variants (via LCSC), FFC + ZIF set, 3–5 duckbill types, needles, silicone sheet + casting kit, M1.2 screws. Measure them with calipers, record the real dimensions here and in `spec/design-parameters.md`, then set the status to LOCKED.
