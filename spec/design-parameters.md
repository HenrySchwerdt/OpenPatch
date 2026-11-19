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

## 2. Envelope dimensions (targets)

| Size | Volume U100 | Target L × W × H (mm) | Omnipod DASH for comparison |
|---|---|---|---|
| OP-70  | 0.70 ml | **38.0 × 32 × 8.5** (CAD ✓) | 52 × 39 × 14.5 mm |
| OP-100 | 1.00 ml | **42.0 × 32 × 8.5** (CAD ✓) | |
| OP-200 | 2.00 ml | **55.4 × 32 × 8.5** (CAD ✓) | |

- **Build height 8.5 mm** (8.0 is not achievable with the 16×5 reservoir: stack = 8.4 mm; only with 0.6 mm reservoir wall + 0.75 mm shell) including housing wall and Velcro surface. Corners R ≥ 4 mm, top slightly domed (pillow shape).
- Housing wall thickness: 0.9 mm (MJF PA12 or SLA resin for prototype; later injection-molded PC/PP).

## 3. Reservoir (flat, "stadium" cross-section)

- Rigid reservoir with **stadium cross-section (slot) 16.0 × 5.0 mm inside** → area A = 5·11 + π·2.5² = **74.6 mm²**.
- Piston stroke: 70 U → 9.4 mm; 100 U → 13.4 mm; 200 U → 26.8 mm (+1.0 mm dead-volume reserve).
- Reservoir wall 0.8 mm, material: COC/PP (insulin compatible). Prototype: purchased raw parts/CNC PP or SLA BioMed resin, **for water tests only**.
- Piston: PP core with cast-in silicone/FKM lip seal (stadium shape) – biggest development risk, dedicated test program.
- Fill septum: silicone Ø 4 mm × 2 mm, on the side, with a fill channel into the reservoir.
- Outlet: channel → stainless-steel hollow needle 30G (Ø 0.31 mm) that pierces the septum of the Insight Flex cannula head.

## 4. Drive — SMA ratchet (decision 2026-11-19: SMA only, no motor)

- **Actuator:** nitinol SMA wire (Flexinol-class, Ø0.10 mm baseline, ~150 gf pull, ~4 % contraction; Ø0.076 mm alternative), length ≥ 12 mm (lever may amplify stroke), ends in **crimp ferrules clamped by screws/spring terminals** on the pod board (no soldering, no cable).
- **Ratchet wheel:** an off-the-shelf catalogue spur gear (module 0.1–0.2, OD ≤ 6 mm) fixed on the leadscrew; selection in `mechanical/gear-selection.md`. Teeth geometry follows DIN 867 from module + tooth count, so only the bore must be adapted.
- **Pawls:** drive pawl on a lever pulled by the SMA wire + return spring; **anti-backdrive pawl**; optionally **two drive pawls offset by half a tooth** to halve the step. Pawls/springs laser-cut from stainless sheet via a PCB **stencil** service (JLCPCB/PCBWay) or etched.
- **Leadscrew/carriage/reservoir:** unchanged (M1.6 × 0.35 in its own lane, carriage arm pushes the stadium plunger).
- **Dose per pulse:** U/pulse = 0.35 mm / (z × k) × 74.6 mm² / 10, k = 1 (single pawl) or 2 (half-tooth pawls). Target ≈ 0.05 U (e.g. z = 56 single pawl → 0.0466 U; z = 28 with two offset pawls → 0.0466 U). Exact value comes from the chosen gear; firmware stores it as an exact rational and has no default.
- **Refill — primary (no crank):** the carriage nut is a spring-closed **half-nut**; the release slider (blocked while docked) opens it, the carriage slides freely and the **injected insulin pushes the plunger back to the rear hard end-stop** (syringe goes hard + detent click). Closing the slider re-engages the half-nut anywhere. Fill level from a **linear carriage-position sensor** (magnet on the carriage + hall/TMAG, ± 1–2 U). Delivery is hard-blocked while released.
- **Refill — fallback (manual rewind, must be foolproof):** a release slider lifts both pawls; the leadscrew is wound back with a small hex key through a socket in the shell (SMA cannot reverse; reverse pulsing would take ~30 min). Requirements: (a) **torque-limiting slip clutch** in the hex socket so over-winding or winding with engaged pawls can never damage threads, nut, pawls or carriage; (b) **hard end-stops** on the housing at both carriage ends; (c) **end feedback**: tactile/audible detent click at full rewind, a fill window with a U scale, and electronic feedback (angle sensor counts turns → BLE "rewound, ready to fill", beep, LED); (d) release slider **mechanically blocked while docked**; (e) a hall sensor detects "pawls released" → delivery hard-blocked (state REFILL). Fill level is reset only after rewind-complete + pawls re-engaged + user-confirmed fill volume, followed by mandatory priming. Anti-siphon: leadscrew stays self-locking.
- **SMA wire is a wear part** (several 100 k cycles/year at ~1000 pulses/day): replaceable with two screws; firmware flags rising pulse energy as "replace wire".
- **Pulse control:** PWM current-controlled heating pulse (~150–200 mA for Ø0.10 mm, 50–200 ms) + cool-down; max rate ≈ 1 pulse/s (bolus 1.5 U/min ≈ 0.54 pulses/s at 0.047 U). Wire resistance measured during the pulse as contraction/temperature feedback.
- **Hardware safety:** SMA current only via the interlock (MCU enable AND TPL5010 latch AND DOCKED) **plus a hardware pulse-width limiter** (monostable/RC gate) so a stuck MCU output cannot heat the wire continuously; one tooth per pulse is a mechanical over-delivery limit.
- **Verification:** each pulse must produce exactly one (half-)tooth of leadscrew rotation = 360°/(z × k) (≈ 6.4° for z = 56): measured by **TMAG5273 angle readout** on the diametric spindle magnet (12-bit angle; the DRV5032 quadrature pair is too coarse for per-pulse checks and stays as a coarse second channel).
- **Occlusion detection:** pulse without the expected angle increment (wire contracts but the wheel does not advance) + rising required pulse energy.
- Superseded: stepper motor drive (NFP-608-26.45 research kept in `mechanical/motor-selection.md` for reference only).

## 4a. Rev A = bench split (decision 2026-11-19)

The fully integrated pod board does not route on 17.1 × 29 mm (see `electronics/fab/STATUS.md`). Rev A is a bench test sample anyway, so it is split in two:

1. **Bench pod** (same housing envelope, same drive/reservoir/cannula pocket as §2–§4): contains only mechanics and a small **pod sensor board** (2-layer, 0.6–0.8 mm, or flex): SMA wire clamp terminals, TMAG5273 angle sensor on the spindle magnet (mandatory), 2× DRV5032 coarse quadrature, 1× dock hall switch, and a **0.5 mm-pitch FPC/FFC connector** (bottom-contact, ZIF, ≤ 1.2 mm high). No battery, no Qi coil, no RF module in the bench pod. An FFC cable leaves the housing through a slot (sealing not required for bench use).
2. **Bench controller board** (≈ 40 × 50 mm, 4-layer 1.6 mm standard, JLCPCB economic/standard PCBA, prefer JLC Basic parts): nRF52840 module **stocked at LCSC** (no consignment), **SMA driver (logic-level MOSFET, current-controlled PWM, current + wire-voltage sense for resistance feedback, hardware pulse-width limiter; 2 channels: drive + refill release)**, the full **hardware interlock** (MCU enable AND TPL5010 latch AND DOCKED → motor supply), USB-C 5 V power + LDO (no battery, no charger for bench), SWD (Tag-Connect + 10-pin 1.27 mm header), test points, a buzzer (space is not an issue here), button, status LED, motor-current sense for occlusion tests, FFC connector to the pod.
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
2. **DASH compatibility mode** – pod-side emulation of the Omnipod DASH BLE protocol, so that Trio talks through the existing `OmnipodKit` (loopandlearn). Reference implementation: `nightscout/ESP-Sim` (GPL-3.0 → firmware part is then GPL-3.0).
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

## 8. Cannula interface (Insight Flex)

- According to the Roche IFU: tubing is pushed onto the connector plate of the cannula head, release by squeezing two side wings → **two-wing snap hook**, not Luer.
- Exact geometry is **not public** → must be measured by the user with calipers (measurement sheet: `mechanical/cannula-measurement.md`). Until then a parametric placeholder in the CAD:
  - Connector plate (assumption): 14 × 10 × 3.0 mm, needle entry in the center, snap groove 1.0 mm on both sides.
- The pod has a receiving pocket on the underside into which the cannula head latches; the 30G needle pierces the cannula septum.
