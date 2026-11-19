# Sealed plunger drive for the OpenPatch bench pod - study, decision, CAD, test plan

Test project: water only, never on a person (`DISCLAIMER.md`).  Scope: find a plunger drive that keeps the reservoir **closed** (no wall slot in the wetted zone),
is **easy to build** (printed parts, catalogue parts, standard tools), and keeps the pod envelope (OP-100: 47.0 x 32.0 x 8.4 mm) as far as physics allows.
Numbers: `drive_envelope.py` (this folder, `python3 mechanical/studies/drive/drive_envelope.py`); CAD: `op_inline.py` (`generate.py --variant bench --drive inline`);
bench test coupon: `op_inline_coupon.py` (`--drive inline --coupon`, files in `coupon/`).

## 0. Verdict

1. **With the current 16 x 5 reservoir a sealed, easy-to-build drive does not fit 47 x 32 x 8.4.**  Any rigid pusher behind the plunger needs about one stroke of dry length at a full
   reservoir.  The easy design built in CAD (PASS) costs **+10.6 / +14.6 / +28.0 mm** (OP-70 / OP-100 / OP-200: 53.6 / 61.6 / 88.4 mm long, width 32.0 and height 8.4 unchanged);
   the new front module of decision 3c (clamp ring + septum + needle, no valve) takes back f mm (not in the CAD; the end-cap agent reports f; **f = 4 mm assumed**, sensitivity 3 / 4 / 5 in section 5).
2. **With f = 4 mm and a wider bore the envelope can be recovered:** 24 x 5 -> **-1.4 / -0.2 / +3.9 mm**, 22 x 5 -> **-0.2 / +1.5 / +7.2 mm** (OP-70 / 100 / 200).  So 47 x 32 x 8.4
   holds for OP-70 (22 or 24 wide) and for OP-100 with a 24 x 5 bore if f >= 3.8 mm (or within the +2 mm allowance with 22 x 5); OP-200 does not hold (+4 ... +7 mm).  This needs a
   new CNC reservoir, a thrust margin of only 1.7 (breakaway basis, 105 mA), the encoder lane replaced and the sensor board wing moved: **a second design round, estimated not built** (section 5).
3. The two physical ways to avoid the length are either a sealed *moving slot* (rodless-cylinder band, slit elastomer: unproven at 5 mm, not easy) or a *flexible push element*
   (tape spring, chain, band: rejected by the owner as too hard to build).  I found no third way; section 4 lists every candidate with numbers.
4. **Decision:** build the **cup drive** (section 6): leadscrew on the reservoir axis, nut at the plunger, screw enters a dry hypodermic tube inside the plunger, motor
   unchanged beside the reservoir, 3-mesh gear chain with an idler.  No slot, no tongue, no carriage; reservoir volume equals the closed-bore model to 0.000 mm3.
5. **Push-only relaxation (decision 3c: pressure fill, no pull strength needed)** makes the cup drive simpler (section 6a): no glued nut, the plunger stack can be loose parts, the retract is
   done by the fluid pressure against a nut that only follows the screw.  It does *not* shorten the drive: the length comes from the dry cup / tail, not from the pull.
6. Open decision for the owner: accept +14.6 mm for OP-100 (drop or re-think OP-200) with the existing 16 x 5 reservoir, or fund the wide-bore round to get OP-70 and OP-100 back into 43 / 47 mm.

## 1. Physics: why one stroke

The plunger moves s (OP-70 / 100 / 200: 9.4 / 13.4 / 26.8 mm at the 16 x 5 bore, 74.6 mm2).  Whatever pushes it must be (a) on the axis behind it, or (b) beside it.
(b) needs a slot through the wall that the pusher travels along; the slot spans the stroke, so at a full reservoir part of the slot lies in front of the plunger = wetted
(the observed leak).  (a) the pusher at full is *behind* the plunger and at empty it is *s further forward*; the part that is behind the plunger at full is either
a rod sticking out of the bore by s, or a dry cup inside the bore of length s.  A rigid single-stage drive therefore costs **s + nut/gear stack** on the axis line:
`length = wall + gear plane + [s + 2.6] + reservoir + dock tail 20.3 + wall`.  Telescoping with N stages saves only s(1 - 1/N) and adds (N - 1) overlap lengths.

Three levers recover length without a flexible element: (i) wider bore (smaller s), (ii) shorter front stack, (iii) hiding the pusher tail beside the axis (needs a
transverse offset = flexible/folded element or the slot).  Sections 3 and 5 give the numbers for (i) and (ii).

## 2. Research (what commercial pumps and the literature do)

Search results are patent abstracts/claims and press text surfaced by web search; legal status and exact embodiments were **not** verified.

* **Telescoping / nested screws are the patented answer to exactly this length problem.**  US 12,329,927 "Multiple telescoping screw-driven pump mechanism with
  anti-rotation of innermost screw keyed to reservoir plunger" describes nested screws that extend from the reservoir's proximal end; it states that no wearable disposable
  patch pump uses this type of mechanism and that efficiency drops with every extra nested screw (thread losses) -
  [USPTO](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12329927).
* US 2014/0094754 / US 9,539,384 "Telescoping piston drive for medical infusion device": compound lead screw of two diameters inside a piston, motor largely inside the piston
  cavity when retracted - [RPX](https://insight.rpxcorp.com/pat/US20140094754A1), [USPTO](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9539384).
  A Tandem patent search result describes a motor inside the lead screw as more compact than a motor parallel to the plunger axis (not confirmed to be the Mobi).
* CA 2,459,952: reservoir with a threaded lead screw and a plunger threaded onto it ("reduces size, complexity and cost, lends itself to disposable devices") -
  [CIPO](https://brevets-patents.ic.gc.ca/opic-cipo/cpd/eng/patent/2459952/summary.html); US 5,954,697 threaded-nut syringe plunger -
  [Google Patents](https://patents.google.com/patent/US5954697).  This is the family of the **cup drive** chosen here (nut at the plunger, screw on the axis).
* US 9,339,607 piston rod with plunger and a lead member telescopically coupled - [uspto.report](https://uspto.report/patent/grant/9,339,607); EP telescopic piston-rod patents
  that keep the device shorter than twice the cartridge length (EP 2393535 / EP 1601396 among the search hits, [EPO](https://data.epo.org/publication-server/rest/v1.2/patents/EP2393535NWB1/document.pdf)).
* Omnipod (Insulet): an Insulet-authored review says plunger translation meters the insulin, actuated by an SMA wire in 0.05 U increments -
  [PMC6313290](https://pmc.ncbi.nlm.nih.gov/articles/PMC6313290); the coordinator adds (US 7,128,727 / 7,144,384, Eros teardown, not re-verified) that leadscrew and gears sit beside the reservoir and
  the screw pushes the plunger, accepting the length; Insulet "double reservoir" patent 12,533,461 (inner reservoir as plunger of the outer one) -
  [Justia](https://patents.justia.com/patent/12533461).
* Medtrum Nano: WO 2017/181324 "unilateral driving mechanism for a portable infusion system" exists; a Medtrum prior-art citation describes a piston connected to a screw inside
  the reservoir - [Google Patents](https://patents.google.com/patent/JP2015530153A5/enExample), [prosecution page](https://insights.ipauthor.com/17434009.html).
  Roche Accu-Chek Solo: step-motor drive, reservoir carries its own piston rod - [PMC7196855](https://pmc.ncbi.nlm.nih.gov/articles/PMC7196855), [package insert](https://www.accu-chekafrica.com/document/accu-chek-solo-reservoir-package-insert-pdf-0/download).
  Ypsomed (YpsoPump/YpsoDose): no drive teardown found, Ypsomed documentation in [ondrugdelivery 2025](https://ondrugdelivery.com/wp-content/uploads/2025/09/176_2025_Sep_Wearables_Ypsomed.pdf).
  EOPatch uses an electro-osmotic pump (not a plunger) and is 14.5 mm thick - [PMC6313281](https://pmc.ncbi.nlm.nih.gov/articles/PMC6313281).
* Open-source syringe pumps: in-line motor + coupler + screw makes the pump longer, minimum length = extended syringe + coupler + motor; a motor beside the screw or a motor with
  integrated leadscrew is the compact fix - [PMC11299592](https://pmc.ncbi.nlm.nih.gov/articles/PMC11299592).  Teardown note: the motor advances a screw that pushes the piston -
  [Hackaday](https://hackaday.com/2023/04/25/insulin-pump-teardown-shows-one-motor-does-many-jobs).

**Reading for us:** the plunger-based designs found either put the pusher behind the plunger and accept the length (thicker pods: EOPatch is 14.5 mm, and it is not plunger-based anyway),
or file telescoping screws (patents; none confirmed in a product at M1.6 scale).  I found no commercial design with a motor beside
the reservoir and a slot through a wall whose slot is wetted; that is the part of the bench pod that has no precedent.  The pod's 8.4 mm height is what forces the pusher into a long line.

## 3. Bore width (the owner's idea): helps, but costs thrust

Height stays 5.0 (cavity 6.6 is already full).  From `drive_envelope.py`:

| bore | area mm2 | stroke 70/100/200 | seal breakaway N (S2, perimeter) | U/step @16:20 | lost motion per 0.1 mm, U |
|---|---|---|---|---|---|
| 16 x 5 | 74.6 | 9.4 / 13.4 / 26.8 | 1.20 | 0.00395 | 0.75 |
| 20 x 5 | 94.6 | 7.4 / 10.6 / 21.1 | 1.45 | 0.00501 | 0.95 |
| 22 x 5 | 104.6 | 6.7 / 9.6 / 19.1 | 1.58 | 0.00554 | 1.05 |
| 24 x 5 | 114.6 | 6.1 / 8.7 / 17.4 | 1.71 | 0.00607 | 1.15 |

* Width available: pod cavity 30.2; motor lane needs 6.1; the reservoir (bore + 1.6 walls) can be at most about 24.0 -> **bore <= 22.4**.  22-24 mm also removes the free
  lane beside the reservoir (the encoder shaft and the sensor wing sit there, section 5).
* Thrust (chain of 3 meshes, 0.0387 N/mA from sim A1, +0.95 x 0.97 per extra mesh): 16 x 5 gives 3.45 N @105 mA, 5.26 N @160 mA, 5.95 N @181 mA.  Margin versus
  *breakaway + duckbill only*: 2.4 / 3.7 / 4.2 at 16 x 5; 1.8 / 2.8 / 3.2 at 22 x 5; 1.7 / 2.6 / 2.9 at 24 x 5 (105 / 160 / 181 mA).  Margin versus the full requirement incl.
  40 kPa occlusion pressure: 0.78 / 1.19 / 1.35 at 16 x 5 and 0.57 / 0.86 / 0.98 at 22 x 5.  **Thrust margin >= 2 (breakaway basis) needs 160 mA for every width; at 105 mA the
  limit is a bore of about 19 mm.**  A z12 motor gear (torque x1.33, U/step x0.75) restores 1.3-1.8 on the full-requirement basis and costs resolution.
* Compliance and lost motion in volume scale with the area (+40 % at 22 x 5, +54 % at 24 x 5); the occlusion force for the same pressure scales the same way.
* **Answer to the question "which bore width minimises length with margin >= 2 and small lost motion":** length falls monotonically with width; the largest width with
  margin >= 2 on the breakaway basis at the *firmware limit of 105 mA* is **19-20 mm**, at 160 mA it is the geometric limit **22.4**.  Lost motion (thread backlash 0.08 mm) is
  0.6 U at 16 x 5 and 0.8 U at 22 x 5 and is removed by the firmware take-up after each draw (sim A2.2: 152 steps).

## 4. Options table (all candidates, sealed reservoir)

Length = pod length per size relative to 43.0 / 47.0 / 60.4 mm.  "Easy" = printed + catalogue parts, standard tools, no forming of spring steel, no fiddly chains.

| # | option | sealed? | extra length OP-70 / 100 / 200 | easy? | verdict |
|---|---|---|---|---|---|
| 1 | tape spring / curved steel band in a U guide | yes | ~0 (needs R >= 3 mm, nitinol or shaped steel) | **no** (owner: rejected) | out |
| 2 | bead / link chain in a U guide | yes | ~0 | no (fiddly, guide inside the bore) | out |
| 3 | telescoping screw (2 stages, catalogue tube + rod + nut) | yes | ~ s/2 + 3: +7.7 / +9.7 / +16.4 | no (M1.6 inside a tube with its own thread; no catalogue nested threads) | out |
| 4a | rodless-cylinder slot band | partly (band must lift under the carriage) | ~0 | no, unproven at 5 mm | out |
| 4b | slit silicone strip over the slot | dynamic, pressure opens the lips | ~0 | printed + cast, but unproven; bench-test idea only | maybe later |
| 4c | rolling diaphragm | yes | needs a rigid pusher through the diaphragm: no gain | no | out |
| 4d | magnetic coupling through the wall | yes | ~0 | easy | **fails**: 1.2 N vs 7 N (`sim/studies/magnetic_coupling.py`) |
| 5a | rigid push rod from the open end, carriage beside | yes | +s ... : +10.9 / +14.9 / +28.3 (push screw row) | easy | works, but off-axis push has an 11.3 mm lever (review: ~5 N guide drag) |
| 5b | **cup drive**: screw on axis, nut at plunger plate, dry tube (built) | **yes** | **+10.6 / +14.6 / +28.0** | **yes** | **chosen** |
| 5c | 5b with bore 22 x 5, motor lane only | yes | +3.8 / +5.5 / +11.2 | no: new CNC reservoir, encoder lane lost, sensor board wing moves | later option |
| 5d | 5c + new front module of decision 3c (f = 4 mm assumed) | yes | 22 x 5: -0.2 / +1.5 / +7.2; 24 x 5: -1.4 / -0.2 / +3.9 | second design round (CNC reservoir, cap, board) | **recommended next round if 47 mm matters** |
| 5e | spring-loaded plunger, screw/cup only as a brake (push-only makes this possible) | yes | no gain: the cup/screw stays; motor torque need falls to ~0.3x because the screw is self-locking | adds a spring in the dry bore | not pursued (note: fill must beat the spring, F/A = 94 kPa at 7 N) |
| 6 | dock beside the reservoir | - | - | does not fit: pocket 15.2 + reservoir 17.6 + walls 1.8 = 34.6 > 32.0 | out |

(A buckling/strain analysis of the tape-spring band had been started and was dropped when the owner rejected the band; no band numbers are claimed here.  Options 3 and 5c/5d lengths are
estimates from `drive_envelope.py` / a heuristic, not CAD.)

## 5. Whole-pod / front-end redesign (coordinator question)

Axis line today (OP-100): wall 0.9 | gears 3.2 | reservoir 21.7 | end cap 4.4 | dock insert 16.8 (x_r1 + 4.4 ... + 21.2; the dome is d10 x 5 high) | wall 0.9 = 47.0.

* (a) **New front module (decision 3c: no check valve, pressure fill by syringe, clamp ring + septum + needle):** the cap block is 4.4 long today (spigot 2.0 into the port, duckbill 3.4 at
  u 0.6 .. 4.0, hub at 4.8).  Without the duckbill and the branch the module can be a clamp ring + septum + needle; the saving f is reported by the seal/end-cap agent, **4 mm is assumed here**
  (sensitivity f = 3 / 4 / 5 in the table below; every mm of f is a mm of pod length for all sizes).  The frozen dock datum (insert x0_u = 4.4 from x_r1) moves by f; that needs a STATUS decision
  entry.  The CAD of this study does **not** include f (it keeps the cap files untouched); subtract f from the CAD lengths.

  Delta length vs 43.0 / 47.0 / 60.4 (cup drive, gear plane 2.6..4.0; `drive_envelope.py` 2b):

  | bore | f = 0 | f = 3 | f = 4 | f = 5 |
  |---|---|---|---|---|
  | 16 x 5 | +9.2 / +13.2 / +26.6 | +6.2 / +10.2 / +23.6 | +5.2 / +9.2 / +22.6 | +4.2 / +8.2 / +21.6 |
  | 20 x 5 | +5.2 / +7.5 / +15.3 | +2.2 / +4.5 / +12.3 | +1.2 / +3.5 / +11.3 | +0.2 / +2.5 / +10.3 |
  | 22 x 5 | +3.8 / +5.5 / +11.2 | +0.8 / +2.5 / +8.2 | -0.2 / +1.5 / +7.2 | -1.2 / +0.5 / +6.2 |
  | 24 x 5 | +2.6 / +3.8 / +7.9 | -0.4 / +0.8 / +4.9 | -1.4 / -0.2 / +3.9 | -2.4 / -1.2 / +2.9 |

  Prior art note (from the coordinator, not re-verified): Omnipod (US 7,128,727 / 7,144,384, Eros teardown) puts leadscrew and gears *beside* the reservoir with the screw pushing the plunger and
  accepts the length; its fill septum is on the underside.  An underside septum would also free the -Y side wall region for this pod.
* (b) **Dock beside/under the motor lane:** the insert window is 13.7 wide, the pocket 15.2 wide; the free lane beside the reservoir is 20.1 ... 31.1 = 11.0 and is occupied by the motor
  (y 25 ... 31) for 17.7 mm.  Moving the dock there means moving the motor to the rear (+17.7 mm) - no gain.  Narrowing the reservoir to a 13.4 bore (outer 15.0) would let the dock sit beside it
  but raises the stroke to 16.2 (OP-100) and still leaves no lane for the motor.  **No gain; not pursued.**
* (c) With (a) at f = 4 mm and a 22-24 mm bore the cup drive costs -0.2 / +1.5 / +7.2 (22 x 5) or -1.4 / -0.2 / +3.9 (24 x 5) for OP-70 / 100 / 200: **47 x 32 x 8.4 holds for OP-70 (both widths)
  and for OP-100 with 24 x 5 (needs f >= 3.8 mm; with 22 x 5 it is +1.5, inside the +2 mm allowance); OP-200 does not hold (+4 ... +7 mm).**  Thrust at 24 x 5: breakaway-basis
  margin 1.7 @105 mA / 2.6 @160 mA, full-requirement margin < 1.1.  Requirements: new CNC reservoir (port off-centre by up to 1.7 mm because the dock needle axis y 11.2 is fixed), cap redesign,
  the encoder shaft lane disappears (idler only), the pod sensor board wing (TMAG + 2 x DRV5032 at y 22.5) must move to the motor axis y 28.0 with the magnet on the motor rear boss, thrust
  at 160-181 mA or a z12 motor gear.  This is a second design round, not an optional switch.

## 6. Chosen design: the cup drive (CAD: `--drive inline`)

```
motor (unchanged, y 28.0) z16 -> gear_b z20 (old lane axis y_s 22.5: ENCODER shaft with magnet under the existing board) -> idler z17 on a fixed pin (y 16.85)
   -> gear_d z20 on the reservoir axis (y 11.2) -> M1.6 screw (axially fixed: thrust sleeve on the dry bush face) -> DIN 934 nut in the plunger rear plate
plunger = rear plate (stadium 15.6 x 4.6 x 3.0: nut pocket, anti-rotation by the bore) + 13G tube (od 2.4 / id 1.8) + piston (core, 2 cast S2 lip rings, 0.7 nose)
```

* **Sealing:** the only moving seal is the plunger lip seals (S2, unchanged).  The reservoir has two openings only: the dry rear end (behind the plunger even when full) and the d2.0
  port.  The screw lives in the dry tube and never touches fluid.  CAD fluid-boundary check: reservoir volume = closed-bore model (diff 0.000 mm3) for every size.
* **Gear ratio / firmware:** gear_b -> idler -> gear_d is 1:1, so one encoder revolution = one screw revolution; the preset g16-20 and U/step 0.00395 are unchanged.  Chain gears:
  centres 5.51 (z16-z20, as now), 5.65 + 5.65 (z20-z17-z20; theory 5.55 + 0.10 backlash window).  Alternative without a z17: z18 idler + z18 nut gear (ratio 1.125).
* **Force path / margins:** plate/nut -> tube (compression 7 N: Euler load of the 2.4/1.8 tube over 26.8 mm is 2.9 kN, stress 3.5 MPa) -> piston.  Thrust 3.45 N @105 mA, 5.26 @160 mA,
  5.95 @181 mA (3 meshes); required: S2 breakaway 1.2 + duckbill 0.22 = 1.4 N (margin 2.4 / 3.7 / 4.2; with decision 3c the duckbill term drops to the needle/septum back-pressure only); with
  40 kPa occlusion pressure 4.4 N (margin 0.8 / 1.2 / 1.35).  Pull is **not required** any more (decision 3c, section 6a).  No tongue (sim 4.4: the tongue allowed 1.4 N) and no 11.3 mm lever.
* **Accuracy:** lost motion is only the nut thread play (0.08 mm assumed = 0.6 U at 16 x 5, 150 steps; 0.15 mm worst = 1.1 U); the old socket + tongue play (2.2 U) is gone.  Train
  compliance 0.016 mm at 7 N = 0.12 U (old tongue: 0.10 U per 3 N).  Firmware take-up after every draw, as sim A2.2 already requires.  A preloaded double nut is the hardware option.
* **Failure modes and detection (existing sensors):** missed steps / jam -> spindle Hall (TMAG on the encoder shaft) angle vs commanded steps; thread jam -> current rise; nut pull-out of the
  plate -> encoder turns but no flow (needs the flow/occlusion model; test the nut retention at 20 N); seal leak into the dry cup -> visible through the fill window over the bore axis (the lid slot
  moved from the lane to the bore axis in `--drive inline`); wall leak: none by construction; end stops: plate at the rear dry strip (1.0), nose 0.3 from the closed end (CAD checks both).
  Buckling: not applicable (tube + guided screw).  Yaw/guide drag: none (on-axis push).
* **Assembly without a soldering iron:** (1) drop the reservoir into the bottom shell; (2) drop the nut into the plate hex pocket (loose, push-only: no glue needed; a dab of silicone only to
  keep it from falling out during assembly), push the tube into the plate counterbore and the piston socket (push fit), cast/fit the two lip rings; (3) slide the plunger assembly into the bore from the rear; (4) push the idler pin (d2.0) into its bore, place gear_c; (5) thread the screw with gear_d + sleeve
  through the dry bush into the nut (turn); (6) encoder rod + gear_b as before; (7) motor, board and lid as before.  Parts to order (new): GHW module-0.3 z17 gear (availability TO VERIFY),
  steel pin d2.0 x 6, 13G hypodermic tube (od 2.41 / id 1.80, cut with a cut-off wheel), 1 more DIN 934 M1.6 nut is *not* needed (the carriage nut moves to the plate); printed: plunger plate,
  thrust sleeve 2 (SLA/MJF); reservoir CNC part is longer by about one stroke (same bore, same frozen port).

### 6a. What the push-only requirement (decision 3c) changes

Requirement now: the coupling must transmit **push** (dose) and a **light retract**; during the syringe pressure fill the fluid pushes the plunger back and the drive only limits the speed.

* Nut: no retention glue.  Dose: the pocket web pushes the nut forward on the screw flank.  Fill: the fluid pushes the plate rearward, the web pushes the nut rearward against the rear flank while the
  screw turns back; the nut never has to pull.  The old risk "nut pull-out under 3 N draw" disappears.
* The plate -> tube -> piston stack can be loose parts (push fit, no glue); the tube is only loaded in compression (3.5 MPa at 7 N).  Tube-to-piston and tube-to-plate joints need no tensile strength.
* Backlash: during retract the plate is pressed onto the nut flank by the fluid; during dose the load flank is the same flank -> after a fill the play is already taken up on the dose flank, the 0.6 U
  take-up (sim A2.2) is needed only when the motor reverses *without* pressure.  Firmware must advance >= 150 steps after a fill before counting dose.
* Pressure fill speed limit: retract speed is limited by the screw turning back; the fluid pressure needed is seal breakaway + back-pressure = 1.4 N / 74.6 mm2 = 19 kPa (a syringe does that easily).
  A slipping nut is impossible in the push direction; in the retract direction the screw can only run ahead of the plunger (no plunger motion without fluid), so a stuck plunger shows as a
  motor/encoder turn without volume: needs the flow/occlusion check on the pod sensors.
* What it does *not* change: the length.  A push-only *tip contact* variant (rotating nut + non-rotating flat screw pushing the plunger, "push screw" row of the tables) needs fewer parts (no tube, no
  plate) but is 1.7 mm longer than the cup and needs a keyed screw tail; kept as the fallback.
* Spring-loaded variant (option 5e): a compression spring in the dry bore costs only its solid length at full, but a screw/cup is still needed as the brake, so no length gain; it would cut the motor
  torque need to about 0.3x (a self-locking M1.6 x 0.35 screw lets the spring push with F x (mu/cos30 - tan(lead)) torque) at the price of a fill pressure above F/A.

### CAD result (`python3 generate.py --variant bench --drive inline` + `python3 check.py --variant bench --drive inline`, outputs in `out/bench-inline/`)

Pod sizes: **53.6 / 61.6 / 88.4 x 32.0 x 8.4 mm** (`check.py` PASS for all three: height 8.4, width 32.0, no solid interference over 48 bodies, no open bodies/fragments, dock insert + 12 variants assemble).
**Fluid-boundary check** (`op_inline.fluid_boundary`, run inside `check.py`): the measured reservoir solid volume equals the closed-bore model (outer stadium - chamber - d2.0 port) to 0.000 mm3 for
OP-70 / 100 / 200 (1044.29 / 1301.71 / 2164.05 mm3), i.e. the wall has no opening except the dry rear end (x 5.50, behind the plunger even when full: wetted zone starts at the piston front at x 19.5 / 23.5 / 36.9)
and the port.  Negative control: the old slotted reservoir of `out/bench/OP-100.sc` measures 858.29 mm3 against 876.97 for a closed bore (-18.7 mm3, tolerance 0.5), so a slot of any useful size fails the check.
The default `check.py --variant bench` still passes (OP-70 re-run).  Default pod and `out/bench/` are untouched; the
switch is additive (`op_inline.py`, small guarded hooks in `generate.py`, `check.py`, `op_build.py`, `op_layout.py`, `op_shell.py`).  What moved relative to the standard pod: reservoir longer by
`s + 0.1` (plunger 3.8 -> cup s + 3.6), gear plane from x 2.6 to 4.0 (the lid screw bosses move behind it: dry screws at y 4.2 / 7.4 / 27.8), carriage + rail + tongue shim removed, drive axis moved
from y 22.5 to y 11.2 with an idler at y 16.85, encoder rod lengthened, fill window over the bore axis.  Not modelled: real STEP component replacement (`_real.sc`) and the exploded/real renders
for this variant, thread and tooth detail, the glue joints.

## 7. Risks and open points

1. **Envelope:** +14.6 mm for OP-100 is a product-level decision; 47 mm is only reachable with the section 5 redesign (not easy).
2. z17 gear availability (GHW); fallback z18/z18 (ratio 1.125, thrust -10 %).  Gear centre distances use `centre_add` 0.10 (sim 3.1 window).
3. Thrust: 3.45 N @105 mA is only 2.4 x the S2 breakaway; with the *old* seal (14 N) it fails as before.  160 mA is needed for margin >= 3.5 or any real occlusion pressure.
4. Encoder rod length 31.6 / 39.6 / 66.4 mm (M1.6) for a pure encoder job: could be replaced by a magnet on gear_c's pin (not done: board and magnet datum unchanged).
5. Piston socket wall 0.55 mm (tube od 2.4 in the 3.6 mm groove floor): SLA/MJF printable, verify.
6. Nut is loose in the plate (push-only): verify it cannot jam or rattle in the pocket (AF 3.3 vs 3.2) and that it follows the screw on a pressure-fill retract (section 8, test 5).
7. Leak of the piston seal into the dry tube would reach the gears: add a bench leak indicator or accept visual inspection.
8. Tube/screw radial clearance 0.1 mm: the screw tip is free in the tube; side loads are tiny but measure drag torque.

## 8. Bench test coupon (build this first, about EUR 10 of printing + parts)

`python3 mechanical/generate.py --variant bench --drive inline --coupon` writes `coupon/*.stl|step` (`drive_coupon.sc` opens in SolidCraft).  Parts: bore block (16 x 5, open at both ends, 32.6 mm,
printed SLA/PA12 or a short length of the real PP reservoir), rear block with the bush seat and a 8 mm access hole, flat front pad, front plug with the d2.0 port, plunger plate, piston core, nose,
2 cast lip rings (existing mould), 13G tube, DIN 934 M1.6 nut, M1.6 rod.  No pod, no electronics.

1. **Seal friction:** remove the screw, hook a spring scale/luggage scale to the plate, fill the bore front with water, pull at constant speed: breakaway and kinetic N (target S2: 1.2 / 0.8 N).
2. **Thrust vs torque:** put the coupon on a kitchen scale (0.1 g resolution; 7 N = 714 g) with the front pad pressing on the scale, turn the screw with a torque screwdriver or a motor + current
   meter: thrust N per N*mm (expected 1/(0.35/(2 pi) + friction terms) ~ 1 N per 0.45 N*mm at mu 0.22).
3. **Leak:** plug on the port, push to the stop with water, 30 min, check the dry rear side with tissue.
4. **Lost motion:** mark the plate edge, reverse the screw, count turns until the plate moves (0.08 mm = 0.23 turn).
5. **Pressure-fill retract (decision 3c):** with the front plug open to a syringe, fill by hand at 20-60 kPa while turning the screw back by hand: the plate must follow the screw without the nut
   jumping a tooth; measure the fill pressure needed (target < 30 kPa) and repeat after 24 h in water.
6. **Endurance:** 200 cycles stroke / draw by hand-driven cordless screwdriver at low speed; re-measure 1.
