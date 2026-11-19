# Safety concept

> **Important:** OpenPatch is a **test project, not a medical device**. It must **never** be worn on the body or used to deliver insulin to a person (see [DISCLAIMER.md](../DISCLAIMER.md)). This safety concept exists so that the engineering is done properly and so that bench tests are meaningful — not to make on-body use acceptable.

## 1. Hazards and countermeasures

| # | Hazard | Cause | Countermeasure (layer) |
|---|---|---|---|
| H1 | **Over-delivery** | Firmware bug, motor runs on, BLE command duplicated, piston "jumps" | (a) Safety supervisor with hard limits, separate from the delivery engine (FW). (b) Motor driver needs **two** enables: MCU GPIO **and** external TPL5010 watchdog (HW). (c) Encoder measures the actual spindle rotation independently of the steps (HW+FW). (d) Sequence numbers and replay protection (protocol). (e) Hourly rolling limit of 15 U. |
| H2 | **Under-delivery / occlusion** | Cannula kinked, pod not latched, air | Encoder slip, current rise, alarm at ≤ 2 U not delivered; docking detection (Hall or contact switch in the cannula pocket) |
| H3 | **Unnoticed delivery stop** | Battery empty, brown-out, crash | Battery warning at 20 %, alarm at 10 %; brown-out reset → pod starts in state **SUSPENDED** and announces itself with an alarm instead of silently continuing; buzzer runs from its own path |
| H4 | **Air in the reservoir** | Filling | Filling instructions with venting, priming required before first docking |
| H5 | **Wrong concentration** | U200 instead of U100 | App requires U100 and the insulin type when filling |
| H6 | **Loss of communication** | BLE gone | Temp basal falls back to the programmed basal rate after at most 30 min; basal continues autonomously on the pod |
| H7 | **Unauthorized access** | Attacker via BLE | Pairing with key exchange (X25519), AES-CCM, no unauthenticated bolus command, pairing only after a button press on the pod |
| H8 | **Insulin degradation** | Heat from charging or electronics, unsuitable materials | Charge only with the pod detached (charge detection → delivery paused + notice); temperature sensor; insulin-contacting parts only from medical-grade PP/COC/silicone. **3D-printed reservoirs for water tests only.** |
| H9 | **Forgot to remove / pod on the charger** | Use | Docking detection: if the pod is not docked, it pauses delivery, alarms after 15 min and reports "not docked" to Trio |
| H10 | **Mechanical backflow / siphon** | Pressure on the housing | Stadium piston with anti-rotation feature, self-locking spindle (M1.6 × 0.35 is self-locking) |

## 2. Hardware interlock (core)

```
            MCU GPIO MOTOR_EN ──┐
                                 AND ──► Load-Switch ──► STSPIN220 VS/VDD
 TPL5010 WAKE/DONE-Watchdog ────┘
       (is "fed" only by the safety task;
        if it stops, motor supply is hard OFF)
```

- The delivery engine must **never** service the watchdog itself. Only the safety supervisor does that, and only when all checks have passed.
- The encoder evaluation runs in the safety supervisor. If steps and rotation deviate by more than 10 % over 1 U, delivery is stopped.

## 3. Bench verification plan (water or insulin into containers, never on a person)

1. Gravimetric delivery accuracy with water on a precision balance with 0.1 mg resolution: 0.05 / 0.5 / 5 U, 50 repetitions each. Target: ±5 % from 1 U.
2. Occlusion test: outlet blocked → alarm before 2 U.
3. 72 h endurance test with water and a basal profile, including BLE disconnects and reconnects.
4. Fault injection: firmware hangs → watchdog switches the motor off (verify with an oscilloscope).
5. Leak tightness: 30 min under water at 1 m depth (IPX7-like).
6. Insulin bench tests (into a vial on a balance, never a person): delivery accuracy with real insulin viscosity, bubble behaviour, material compatibility (insulin-contact parts only from PP/COC, medical silicone, stainless steel — never printed resin), insulin stability in the reservoir over 48 h at 37 °C (visual/fibrillation check). Start with a standard 1 ml U100 insulin syringe as the reservoir (syringe bench rig), then the CNC-PP stadium reservoir.
7. There is **no** step 7. The project never proceeds to use on a person.
