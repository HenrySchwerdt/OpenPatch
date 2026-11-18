# OpenPatch – Shared Design Parameters (Single Source of Truth)

> All subprojects (mechanical/, electronics/, firmware/, ios/) MUST use these values.
> Make changes only here, then propagate them to the subprojects.
> Status: Concept v0.1 (2026-11-18). Experimental DIY device, NOT an approved medical device.

## 1. Product concept

- Reusable, detachable patch pump ("pod") that is plugged directly onto the cannula head of an
  **Accu-Chek Insight Flex** infusion set (Roche, 6/8/10 mm) – no tubing.
- Attachment to the body: Velcro (hook side on the pod base, loop side on a medical adhesive patch
  around the cannula) – the pod is detachable (showering, sports), the cannula stays in place.
- Filling with a syringe through a silicone septum (like Omnipod), insulin U100.
- Inductively chargeable (no connector hole → easier to make waterproof).
- Three variants that differ ONLY in reservoir/housing length: **70 U, 100 U, 200 U**.

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

## 4. Drive

- Micro stepper motor **Ø 6 mm** (ref.: Faulhaber ADM0620 / FDM0620, 2-phase, 20 steps/rev, 3 V) transverse next to the reservoir.
- Rev A motor: **Zhaowei ZWBPD006006** (Ø6 mm, planetary **i = 5:1**, 23.7 mm long, AliExpress ~$10–25; premium preset Faulhaber ADM0620 + 06/1 16:1). Ratio and 20 steps/rev must be confirmed with the seller.
- Threaded spindle **M1.6 × 0.35** (brass/stainless steel) **in a dedicated track NEXT TO the reservoir**; nut carriage with an arm that pushes the piston through a slot at the reservoir end (inline would be ~2× stroke length → 48/56/83 mm).
- Resolution (Rev A, 5:1): 0.35 mm / (20·5) = 3.5 µm/step → **0.261 µl/step = 0.0261 U/step** (Faulhaber 16:1: 0.0082 U/step).
- Smallest bolus/basal pulse: **0.05 U ≈ 2 steps** (actual value 0.0522 U; firmware accumulates the remainder).
- Spindle encoder: magnet on the spindle + Hall sensor (e.g. TMAG5273 / AS5600L class) for **independent delivery verification**.
- Occlusion detection: motor current/back-EMF rise + encoder slip (no travel despite steps).

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
