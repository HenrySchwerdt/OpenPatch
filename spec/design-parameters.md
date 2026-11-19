# OpenPatch – Shared Design Parameters (Single Source of Truth)

> All subprojects (mechanical/, electronics/, firmware/, ios/) MUST use these values.
> Make changes only here, then propagate them to the subprojects.
> Status: Concept v0.2 (2026-11-18, two-pod system). Experimental DIY device, NOT an approved medical device.

## 1. Product concept

- Reusable, detachable patch pump ("pod") that is plugged directly onto the cannula head of an
  **Accu-Chek Insight Flex** infusion set (Roche, 6/8/10 mm) – no tubing.
- Attachment to the body: Velcro (hook side on the pod base, loop side on a medical adhesive patch
  around the cannula) – the pod is detachable (showering, sports), the cannula stays in place.
- Filling with a syringe through a silicone septum (like Omnipod), insulin U100.
- Inductively chargeable (no connector hole → easier to make waterproof).
- Three variants that differ ONLY in reservoir/housing length: **70 U, 100 U, 200 U**.

## 1c. Builder experience for the final design (Rev B, requirement, 2026-11-19)

- Anyone must be able to build the final pod **without a soldering iron and without loose cables inside the pod**.
- Rev A (bench) may use the motor's factory lead into the controller board; this is a bench-only shortcut.
- Rev B primary: **SMA (nitinol) ratchet drive** — wire ends in crimp ferrules clamped by screws/spring terminals on the PCB (drive and contact in one, no motor, no cable).
- Rev B fallback if a motor stays: motor with a **short FPC tail into a ZIF connector** (custom NFP option, MOQ 100–500 → organised as a community group buy), or motor pins THT-soldered by the PCBA house (consigned motors) so builders receive the board with the motor already fitted.

## 1b. Two-pod system (concept v0.2, proposed by the user 2026-11-18)

- A user owns **two identical pods (A/B)**. One is docked on the cannula and delivers; the other sits on the Qi charger and is refilled.
- **Max wear time per pod: 48 h** (warning at 44 h, delivery stop + alarm at 52 h). Insulin stays well under the ~3-day in-pump limit.
- Size choice: OP-100 covers up to ~50 U/day for 2 days (incl. priming); OP-200 for higher TDD; OP-70 up to ~30 U/day.
- Battery requirement drops to **≥ 2 days + 50 % reserve** (≈ 7–10 mAh at ~100 µA average, estimate) → the Rev A cell (17–26 mAh) is sufficient.
- **Only one pod may ever deliver.** Enforced by two independent conditions:
  1. **Dock detection (mandatory):** a magnet in the cannula adapter + Hall switch on the PCB; a pod that is not docked never delivers (hardware input to the safety supervisor).
  2. **Explicit handover:** the app sends `Release` to the old pod and waits for its confirmation (delivery stopped, delivered total reported) before sending `Activate` to the new pod with the current basal schedule, active temp basal and remaining IOB context. The pod refuses `Activate` while another pod in the same pair has not confirmed release (pair ID + role in the protocol).
- Trio sees **one** pump (OpenPatchKit manages the A/B pair internally). DASH compatibility mode remains possible, but every swap is a new "pod" with fresh pairing, so the native kit is the primary path.

## 1a. Assembly without a soldering iron (requirement)

- All electronics are assembled by PCBWay; battery and motor are contacted via **SMD spring contacts (≤ 1.2 mm)** that the lid presses on.
- Qi coil: trace coil on the board or assembled by PCBWay.
- Housing: screws/snap hooks; tools: tweezers, small screwdriver, UV lamp.

## 1d. Cost target (decision 2026-11-19, user)

- **One complete bench pump (pod + controller, Rev A) costs ≤ 200 € all-in**, sourced AliExpress-first (LCSC/JLCPCB for PCBA, JLC3DP for prints, PCBWay only where unavoidable): all parts, PCBs/PCBA, prints, reservoir, consumables for one fill, shipping and import VAT/duty to Germany included.
- Excluded: one-time tools (calipers, scale, programmer/nRF52840-DK, screwdrivers) — listed separately in `docs/SHOPPING.md`.
- Minimum-order overhead (e.g. 5 PCBs, CNC setup) is allocated to the first pump; the marginal cost of further pumps is reported separately.
- Safety-relevant parts (interlock, watchdog, hall/angle sensors, insulin-contact materials) are never downgraded to meet the cost target.

## 2. Envelope dimensions (targets)

| Size | Volume U100 | Target L × W × H (mm) | Omnipod DASH for comparison |
|---|---|---|---|
| OP-70  | 0.70 ml | **43.0 × 32 × 8.4** (bench pod, CAD ✓; integrated variant parked) | 52 × 39 × 14.5 mm |
| OP-100 | 1.00 ml | **47.0 × 32 × 8.4** (bench pod, CAD ✓) | |
| OP-200 | 2.00 ml | **60.4 × 32 × 8.4** (bench pod, CAD ✓) | |

- **Build height 8.5 mm** (8.0 is not achievable with the 16×5 reservoir: stack = 8.4 mm; only with 0.6 mm reservoir wall + 0.75 mm shell) including housing wall and Velcro surface. Corners R ≥ 4 mm, top slightly domed (pillow shape).
- Housing wall thickness: 0.9 mm (MJF PA12 or SLA resin for prototype; later injection-molded PC/PP).

## 2b. Size targets for the integrated pod v0.1.0 (decision 2026-11-19, user: "nobody wants a 7 cm pump")

- Hard targets incl. battery and electronics: **OP-100 ≤ 45 mm**, **OP-200 ≤ 52 mm** (Omnipod DASH: 52 × 39 × 14.5 mm, 200 U), width ≤ 32 mm, height ≤ 8.5 mm. A design that misses them is not accepted silently; the gap and the next lever are reported.
- Levers, in order: (1) stack battery + board above the dock tunnel (≈ 3 mm free above the cannula head) instead of a tail; (2) low-profile radio (≤ 1.3 mm) on the lid side + spring contacts instead of connectors; (3) coaxial leadscrew in the reservoir axis (Omnipod-style) + wider bore → shorter stroke; (4) minimal fluid path without valve (§3c).

## 2c. Sizes for v0.1.0 (decision 2026-11-19, user)

- **Two sizes only: OP-100 and OP-200.** OP-70 is dropped (with OP-100 ≤ 45 mm a separate 70 U pod is not worth the extra CAD, tests and reservoir orders). Existing OP-70 bench files stay as history; new work targets OP-100 and OP-200.

## 2d. USB-C instead of charge pads; split boards allowed (decision 2026-11-19, user)

- v0.1.0 gets a **waterproof USB-C receptacle (IPX7-rated with gasket)** at a pod edge where the height allows (~3.2 mm body): charging (5 V → charger), **firmware flashing via the nRF52840's native USB** (USB bootloader/DFU; the debug probe is only needed for debugging), and a USB serial log for bench data. Charge pads, the charging cradle and pogo pins are dropped. This replaces the earlier "no connector hole" rationale of §1 for v0.1.0; Qi/pads may return in a later revision.
- The electronics may be **split into several small boards** (e.g. main: radio + safety chain + motor driver above the dock tunnel; USB/charger board at the edge; sensor board at the spindle magnet), connected **without soldering** (FPC/FFC + ZIF, or spring contacts), produced as one JLC panel.
- The safety chain stays complete; firmware updates over USB must use the signed-image bootloader (no unsigned code path), and USB data must never be able to command delivery without the same authorisation as BLE.

## 2a. Transparent lid (decision 2026-11-19, user)

- The lid is printed in **clear resin** (JLC3DP clear SLA, polished/clear-coated outside) so reservoir, water level, plunger and drive are visible. The **fill window slot in the lid is removed**; the fill scale (ticks every 10 U, long every 50 U) becomes a shallow engraving on the lid inner face above the plunger travel.
- Everything under the lid is therefore visible: tidy cable routing, no labels needed inside; light-sensitive parts (none in the bench pod) must be checked for v0.1.0 (e.g. hall sensors are fine, the TMAG is fine; LEDs may light up the housing).
- Wall thickness and stiffness rules unchanged; clear resin is water-only like all printed parts.

## 3. Reservoir (flat, "stadium" cross-section)

- Rigid reservoir with **stadium cross-section (slot) 16.0 × 5.0 mm inside** → area A = 5·11 + π·2.5² = **74.6 mm²**.
- Piston stroke: 70 U → 9.4 mm; 100 U → 13.4 mm; 200 U → 26.8 mm (+1.0 mm dead-volume reserve).
- Reservoir wall 0.8 mm, material: COC/PP (insulin compatible). Prototype: purchased raw parts/CNC PP or SLA BioMed resin, **for water tests only**.
- Piston: PP core with cast-in silicone/FKM lip seal (stadium shape) – biggest development risk, dedicated test program.
- Fill septum: silicone Ø 4 mm × 2 mm, on the side, with a fill channel into the reservoir.
- Outlet: channel → stainless-steel hollow needle 30G (Ø 0.31 mm) that pierces the septum of the Insight Flex cannula head.

## 3a. Reservoir = frozen CNC interface (decision 2026-11-19)

- The reservoir is a **CNC-machined polypropylene part** (PCBWay CNC), ordered **once per size** (qty 2 incl. spare) and then never changed.
- It is deliberately minimal: stadium bore 16.00 × 5.00 mm (R2.50 = Ø5 end mill), open dry end, one simple port at the closed end. **No septum, valve, needle or dock features in the CNC part.**
- Fill septum, duckbill check valve and needle hub live in a separate, cheap **end cap** pressed onto the port; housing, dock and cap iterate around the reservoir.
- Its envelope, datum faces, mounting features and port position are **frozen parameters** (`mechanical/params.json` → `reservoir_frozen`). Changing them requires an explicit decision recorded in `docs/STATUS.md`.
- Before ordering: independent DFM review of the drawing + PCBWay's quote DFM feedback.
- **Water only (decision 2026-11-19): the pump is never filled with insulin or any drug, not even into containers.** The wetted-path material choice (PP reservoir, medical platinum-cure silicone seals/septum/duckbill, stainless needle; never printed resin) is kept only as design preparation for a future legal manufacturer; the CNC PP reservoir is optional for this project.

## 3b. Plunger coupling: closed reservoir required; same-envelope drive under study (2026-11-19)

- Finding: the previous side-slot coupling (carriage tongue through a slot in the +Y reservoir wall) leaks: the slot must span the whole stroke, so at a full reservoir about 12 mm of slot lie in front of the seal, in the water. It also pushed the plunger 7.2 mm off-axis (cocking).
- Magnetic coupling through a closed wall (keeps the dimensions) was **rejected by simulation** (`mechanical/sim/studies/magnetic_coupling.py`, magpylib, N52): about 1.2 N maximum shear for magnets that fit the plunger (1.2 mm gap), about 3 N with a doubled plunger length, versus about 1.6 N needed just to move (seal breakaway + duckbill) and about 7 N with occlusion back-pressure (30 kPa × 74.6 mm²) and a safety factor of 2.
- **Status (2026-11-19, user): the form factor must stay (OP-100 47 × 32 × 8.4 mm).** A same-envelope sealed drive (tape-spring push band turning 180° around the open end, chain, telescoping screw, …) is being studied (`mechanical/studies/drive/`). The rigid push rod below is the **fallback only**.
- Fallback: the carriage (beside the reservoir) carries a rigid yoke behind the open dry end and a **push rod on the bore axis** that engages the plunger centre (push and pull, for draw mode). The reservoir is a **closed tube without any wall opening** (only the port at the closed end; re-freeze `reservoir_frozen` before ordering). Width and height stay; length grows by about one stroke (OP-100 about 47 → 60 mm).
- Study for a later, shorter revision: a flexible push element (spring-steel band or beaded chain in a U-shaped guide) turning around the open end (about +5 mm instead of +stroke).

## 3c. Fluid path without a check valve: Omnipod-style pressure fill (decision 2026-11-19, user)

- Reference: Omnipod (Eros teardown arXiv 1709.06026, US 7,128,727 / 7,144,384) has no check valve in the sources found; free flow is prevented by a non-back-drivable drive and a closed outlet; filling is done by syringe pressure through a small septum while the plunger moves back.
- **No check valve.** Anti-siphon / anti-free-flow comes from the **self-locking drive** (M1.6 × 0.35 leadscrew + 26.45:1 gearhead cannot be back-driven by reservoir pressure; verify by a bench test: 50 kPa on the reservoir, no plunger motion with the motor unpowered).
- **Refill = pressure fill:** pod undocked + suspended; the user pushes water with a syringe through the fill septum while the motor **retracts the plunger at a fixed rate** (firmware "assisted fill"); the reservoir stays at positive pressure so no air can enter through the outlet needle; excess exits as drops at the needle tip, which also primes it. Suction draw (motor pulling a vacuum) is **not used** any more. Replaces the earlier automatic draw-mode decision.
- **Fluid module = minimal:** reservoir port → small septum chamber (fill) → outlet needle, held by a printed clamp ring with defined septum squeeze and an O-ring/face seal to the reservoir; no valve, no branching channels.
- Firmware: the reverse motion during fill is rate-limited and stall-monitored; the fill volume is booked from the plunger travel; a prime follows before docking.

## 4. Drive — geared micro stepper + direct leadscrew, automatic refill (decision 2026-11-19)

Rationale: buildability beats minimal size (builders are not watchmakers). No off-the-shelf integrated micro linear actuator meets force/drawing/orderability (`mechanical/linear-actuator-selection.md`); the SMA ratchet needs too many fine custom parts. SMA research stays as a later option for minimal size.

- **Motor:** **NFP-608-26.45-SGM** (Ø6.0 mm, body 15.1 mm, 20 steps/rev, 2-stage ratio 26.45, 4.8 V, 26.5 Ω/phase, shaft Ø2.0 with D-flat 1.5; vendor drawing in the datasheet PDF). ~$6.60 at nfpshop.com.
- **Coupling (2026-11-19, final, supersedes 15:12 and 18:18):** motor **beside** the reservoir (parallel axes) driving the leadscrew through a **purchased step-down gear pair**, GHW-Modellbau module 0.3: **16 T on the motor (390754, bore 2.0) : 20 T on the screw (753020, bore 2.0, hub turned off)**, ~19 €; theoretical centre 5.40 mm, **built centre 5.51 mm**. Reason (real CAD geometry): 15:12 (centre 4.05) and 15:15 (4.50) cannot clear the carriage lane (centre >= 5.5 needed with the 4.8 mm carriage), 20:16 does not fit the 6.7 mm cavity (tip OD 6.6 on the motor), 18:18 fits but costs 32 € and gives less thrust. **Firmware preset `drive-nfp-608-26-45-g16-20` (id 0x25, screw advance per motor turn 0.8, total ratio 26.45 / 0.8 = 33.0625, exact rational 2 088 800 / 529 uU = 3 948.6 uU/step) is the default of `firmware-rs/scripts/build.sh`; `drive-nfp-608-26-45-g15-12` (ratio 21.16) and `g1-1` (26.45) stay as options but are WRONG for this pod.** The coaxial sleeve option remains in CAD (`bench.drive_layout = coaxial`).
- **Leadscrew/carriage/reservoir:** M1.6 × 0.35 leadscrew in its own lane, fixed nut in the carriage, carriage arm pushes the stadium plunger (unchanged).
- **Resolution:** U/step = 0.35 × (16/20) / (20 × 26.45) × 74.63 / 10 = **0.003951 U/step** (16:20 pair); 0.05 U ≈ 12.7 steps; exact rational in firmware, no default.
- **Thrust:** pull-out 1.6 gf·cm × 26.45 × ~0.64 gear eff. ≈ 2.65 N·mm → ≈ 9.5 N at 20 % screw efficiency (≥ 5 N required; verify on the bench).
- **(superseded by §3c: pressure fill, no check valve)** Refill = automatic draw mode (no crank, no slider): pod undocked + suspended → user selects the fill amount in the app → holds the syringe/vial needle in the septum → the motor **retracts exactly that volume and draws the insulin in**, then stops by itself (100 U ≈ 20 s). A **one-way duckbill check valve in the outlet** prevents air being drawn in through the outlet needle (and adds anti-siphon / anti-free-flow protection). Rear end-stop on the housing + stall detection; fill level known exactly from step count + encoder.
- **Encoder:** TMAG5273 angle sensor on a diametric magnet at the leadscrew end (per-revolution verification and stall detection); DRV5032 pair optional.
- **Occlusion:** encoder slip + motor-current rise; duckbill cracking pressure accounted for.
- **Connection:** Rev A bench: factory lead + JST 1.25 into the controller board; Rev B: motor with FPC tail into a ZIF connector (group buy) — no soldering, no cable in the pod (§1c).
- Superseded concepts: SMA ratchet (`mechanical/gear-selection.md`), half-nut pressure refill, hex rewind.

## 4b. Motor candidates for v0.1.0 (2026-11-19, `docs/MOTOR-RESEARCH-2026-11-19.md`)

- On a 1-cell Li-Po without boost the NFP-608-26.45 (26.5 Ω, rated 4.8 V) loses up to ~30 % torque at 3.0 V; v0.1.0 therefore needs either a **5 V boost / current-regulated drive** or a low-voltage motor.
- Size candidate: **Zhaowei Ø3.4 mm stepper + planetary gearbox (ZWBMD004004-36 / -216)**, 3.0 V / 50 mA rated, 13.3–14.8 mm long, driving the screw directly (coaxial). Pull-out torque/resistance/price unverified → order samples and measure thrust on the real screw (water only) before adopting. Fallbacks: Faulhaber FDM0620, or NFP-608 + boost.

## 4a. Rev A = bench split (decision 2026-11-19)

The fully integrated pod board does not route on 17.1 × 29 mm (see `electronics/fab/STATUS.md`). Rev A is a bench test sample anyway, so it is split in two:

1. **Bench pod** (same housing envelope, same drive/reservoir/cannula pocket as §2–§4): contains only mechanics and a small **pod sensor board** (2-layer, 0.6–0.8 mm, or flex): TMAG5273 angle sensor on the spindle magnet (mandatory), optional 2× DRV5032, 1× dock hall switch, and a **0.5 mm-pitch FPC/FFC connector** (bottom-contact, ZIF, ≤ 1.2 mm high). No battery, no Qi coil, no RF module in the bench pod. An FFC cable leaves the housing through a slot (sealing not required for bench use).
2. **Bench controller board** (≈ 40 × 50 mm, 4-layer 1.6 mm standard, JLCPCB economic/standard PCBA, prefer JLC Basic parts): nRF52840 module **stocked at LCSC** (no consignment), **STSPIN220 stepper driver with motor-current sense** (SMA channels optional/DNP), the full **hardware interlock** (MCU enable AND TPL5010 latch AND DOCKED → motor supply), USB-C 5 V power + LDO (no battery, no charger for bench), SWD (Tag-Connect + 10-pin 1.27 mm header), test points, a buzzer (space is not an issue here), button, status LED, motor-current sense for occlusion tests, FFC connector to the pod.
3. Target **≤ $80 per iteration** (5 controller PCBs with 2 assembled + 5 pod sensor boards assembled) so that at least one iteration per month is affordable.
4. The integrated single-board pod is postponed to Rev B (with SMA drive freeing space).

## 5. Electronics

- MCU/BLE: Rev A **Insight SiP ISP1807** (nRF52840 SiP, 8×8×1 mm, integrated antenna); Rev B **nRF54L15** bare chip. No custom ASIC (not manufacturable at PCBWay, cost >> 500 €).
- Motor driver: **ST STSPIN220** (QFN 3×3, 1.8–10 V) or TI DRV8834; **motor enable gated in hardware via a second path** (safety watchdog, see docs/02-safety.md).
- Independent watchdog: TI **TPL5010** (external nano-power timer) → switches off the motor driver supply if not serviced.
- Battery (Rev A, CAD-verified): flat Li-Po, max **8.6 / 12.6 / 13.2 × 11.2 × 3.2 mm** for OP-70/100/200 → est. **~17 / 25 / 26 mAh**, with PCM. Accepted for Rev A (bench test sample only, decision 2026-11-18); Rev B targets ≥ 40 mAh.
- Charging: **Qi receiver TI BQ51003** (2.5 W class) + charge controller **BQ25120A** (or MCP73832), receiver coil **Ø 17.6 mm flat (Ø20 costs +2.4 mm length), on flex PCB or Würth 760308101xxx class**. Alternative later: NFC-WLC (ST25/PTX30W).
- Buzzer: ⚠️ 9 × 9 × 2 mm piezo does NOT fit (free space only 1.6 / 5.6 / 6.2 × 2.6 mm). Rev A: no buzzer (alarms via BLE/Trio only; optional DNP footprint ≤ 5 × 2.6 mm); Rev B must have an audible alarm. Top-side component height under the coil: 1.4 mm.
- Button: 1× (emergency stop / alarm acknowledgment), through a housing membrane.
- PCB: 4-layer, 0.6 mm; shape: rectangle with L-cutout (outline from mechanical/out/OP-xx.layout.json).
- Height stack (away from the body): base 0.9 | battery 3.2 | PCB+components 1.6 | lid 0.9 → remainder coil/tolerance. Reservoir+motor lie in the same plane as battery+PCB (side by side, not stacked).

## 6. Radio / protocols

1. **OpenPatch protocol (native)** – dedicated BLE GATT profile, openly documented in `docs/04-protocol.md`, Trio integration via the dedicated LoopKit PumpManager kit `OpenPatchKit`.
2. **DASH compatibility mode** – pod-side emulation of the Omnipod DASH BLE protocol, so that Trio talks through the existing `OmnipodKit` (loopandlearn). Behavioural reference only: `nightscout/ESP-Sim` (GPL-3.0). **Licensing note:** the DASH mode must be an independent clean-room implementation of the protocol; no GPL code from nightscout/ESP-Sim may be copied, otherwise it cannot be combined with the PolyForm Noncommercial firmware (see `LICENSE.md`).
3. **Omnipod 5**: is NOT emulated – O5 pairing uses P-256/ECDSA-signed transcripts and an external key manager with App Attest; DASH mode covers Trio.

Note: In DASH mode Trio "sees" a 200 U pod with 80 h lifetime; reservoir display from < 50 U, as with DASH. Native mode shows real values, battery, reusability.

## 7. Safety limits (firmware defaults, hard-coded as upper bounds)

- Max. single bolus: 10 U (configurable ≤ 25 U)
- Max. basal rate: 5 U/h (configurable ≤ 30 U/h)
- Max. delivery per hour (total): 15 U
- Bolus speed: 1.5 U/min
- Occlusion alarm: ≤ 2 U undelivered amount
- Communication loss: temp basal continues for max. 30 min, then falls back to the programmed basal rate (DASH semantics)
- Encoder deviation > 10 % over 1 U → delivery stop + alarm

## 7a. Diagnostics and hardware independence (requirement, 2026-11-19)

- **Hardware independence:** the motor supply is gated in hardware (`MCU_EN AND watchdog latch AND (DOCKED OR DIR_REV)`, TPL5010, hardware over-current cut that clears the latch) so that a firmware fault cannot hold the motor on beyond one watchdog interval, and an undocked pod cannot deliver forward. **Hardware step budget (HW-A, decided 2026-11-19, mandatory for v0.1.0; the bench controller Rev A does not have it — documented residual risk in `electronics/bench/INTERLOCK.md`):** an arm window + pulse budget in discrete logic bounds a runaway inside the watchdog window to ≈ 1.6 U; Rev B adds an independent monitor for the hourly limit. Firmware must **prove at runtime** that each gate can still cut the supply (rotating single-gate disarm, POST-A). A proven-stuck gate or a dead watchdog latches the pod; no delivery with a degraded protection layer. The dose limits of §7 are additionally enforced by the firmware supervisor.
- **v0.1.0 safety architecture (decision 2026-11-19, user):** a **tiny independent supervisor MCU** (≈ 2 × 2 mm, e.g. MSP430FR2000 or STM32C011; own firmware, own clock, own supply rail) implements the watchdog window and the HW-A step budget (counts STCK itself) and can cut the motor supply on its own; the **over-current cut and the two series supply switches stay pure hardware**; dock = 2-of-2 hall sensors. The main MCU can never switch the motor on without the supervisor's consent. The supervisor firmware is separate, minimal, test-first and fully specified (state machine in `electronics/v010/INTERLOCK.md`).
- **Diagnostic codes:** every anomaly gets a 32-bit code (layer, component, fault, instance) with severity (info, warning, fault, latched), field-replaceable unit (FRU) and recommended action; the catalogue (`docs/06-diagnostics.md`, generated source `spec/diag-codes.csv`) is the single source for firmware, protocol and app. Codes are never reused. Unknown codes are treated as faults. Latched codes have **no service override**; they clear only when their verification test passes.
- **Propagation:** no layer may swallow a code. A layer that acts on a lower-layer fault raises its own record with a cause pointer. Records persist in a pod fault log, are readable with `GetFaultLog`, and are pushed as alerts. The 8 legacy fault bits remain as a derived projection.
- **Presentation:** Trio shows the pod (A/B), the faulty part and the action ("Replace the controller board"), and a component health view (green/yellow/red per FRU). A part is green only after a passing proof; unproven is grey.
- **Rule for changes:** adding a failure mode requires a catalogue row with hazard link and test; relaxing a severity or a threshold requires an entry in `docs/STATUS.md`.

## 8. Cannula interface (Insight Flex)

- According to the Roche IFU: tubing is pushed onto the connector plate of the cannula head, release by squeezing two side wings → **two-wing snap hook**, not Luer.
- Exact geometry is **not public** → must be measured by the user with calipers (measurement sheet: `mechanical/cannula-measurement.md`). Until then a parametric placeholder in the CAD:
  - Connector plate (assumption): 14 × 10 × 3.0 mm, needle entry in the center, snap groove 1.0 mm on both sides.
- The pod has a receiving pocket on the underside into which the cannula head latches; the 30G needle pierces the cannula septum.

## 8a. Modular dock insert (decision 2026-11-19, user)

The Insight Flex fit is the slowest thing to get right, so it is isolated in **one small, cheap, swappable part**:
- **Dock insert** (printed, e.g. JLC3DP SLA or PA12): contains *all* cannula-specific geometry — pocket, snap arms/latch, needle guide/centring onto the cannula septum, and the dock magnet seat. It is the only part iterated for the fit.
- **Frozen dock interface on the pod** (`mechanical/params.json` → `dock_interface_frozen`, like `reservoir_frozen`): mechanical mount (e.g. dovetail/rail + one M1.2 screw or a snap, tool-free swap), datum faces, needle exit position and axis, dock-hall sensor position (fixed in the pod), magnet-to-sensor geometry. Changing it requires a decision in `docs/STATUS.md`.
- The 30G needle stays in the pod (end cap); the insert only guides/centres the cannula onto it. Needle length is set per insert variant via an insert-side stop, not by changing the pod.
- Every order contains a **variant set of inserts** (parameter sweep, e.g. 8–12 variants, labelled by embossed ID) so the fit can be iterated without rebuying the pump; a pod-less **fit-test coupon** uses the same interface.
- A dummy cannula head (`cannula_adapter`) with the same interface lets the dock be tested on the bench without a real cannula.
