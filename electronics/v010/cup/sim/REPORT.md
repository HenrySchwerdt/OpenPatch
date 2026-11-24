> TEST ONLY - NOT FOR HUMAN USE (see ../../../../DISCLAIMER.md). Water only, never worn.

# SPICE verification of the cup v4 board (power, cut path, enable logic, motor drive)

**Re-run 2026-11-24 for the driver swap (DRV8835 -> 2 x DRV8838, `../../INTERLOCK.md` I.6b):** the behavioural bridge now uses the DRV8838 on-resistance (280 mOhm typ instead of 305). Case 4 still PASS: 0.184 A per coil, supply peak 0.368 A, no fault. Cases 1-3 move by less than 0.2 %; the collapse cases (3.0 V and 3.4 V cell with 1.2 / 1.6 ohm) still collapse, only the sampled value at the stop instant differs (it is taken during the collapse). The text below names the DRV8835; the truth table and the results apply to the DRV8838 pair.

Run everything with `./run_all.sh`, which takes about 12 minutes. `fetch_models.sh` downloads the TI model zips into `models/`. That folder is gitignored because of the TI licence.

The simulated design is the **corrected** netlist from the 2026-11-20 netlist review:
- the gate is `DOCKED XOR DIR_REVERSE` (74AUP1G86);
- a 3-input AND combines `LATCH_Q`, `SUP_PERMIT` and `MCU_EN`, with R18 100 k pulling `MCU_EN` down;
- R26 is 6.8 k (TPL5010 ≈ 2 s);
- the VBUS/VBAT/VMOT capacitors are rated 10 V, plus 4.7 µF on 3V3.

## Models

| Block | Model |
|---|---|
| TPS2553 | TI PSpice model, syntax-converted for ngspice (`spice_compat.py`) |
| TPS61023 | The TI model converts but is **not physical** in ngspice: with TI's own start-up circuit VOUT runs to 6 V at near-zero input current (`summary.json` → `physical: false`). It is replaced by a **behavioural averaged model** (`lib/tps61023_beh.inc`, clearly labelled, not a TI model). Validation: start-up 740 µs against 700 µs in the datasheet, and the max-power collapse point of the cell within 0.01 V. |
| 74AUP gates, latch, DRV8835 bridges | behavioural |
| TPL5010 | datasheet-timed reset waveform, not an IC model |

Assumptions, all to be measured on the bench:

| Parameter | Value used | Sweep |
|---|---|---|
| Ampul 301030 internal resistance | 0.8 Ω | 0.5–1.6 Ω |
| Motor coil inductance | 5 mH | 2–15 mH |
| STM32C011 NRST pull-up | 40 k | – |
| STM32C011 brown-out reset | 1.7 V | – |
| 22 µF effective capacitance at bias | 8 µF | – |

## Results

| Case | Verdict | Key numbers |
|---|---|---|
| 1a Boost start-up | PASS | 0.69 ms to 4.8 V; inrush ≈ 1.0 A for 25–35 µs |
| 1b Bulk capacitor sizing | PASS | 8 µF effective ≥ 4 µF datasheet minimum; ripple ≈ 18 mV (analytic) |
| 1c Cell droop at motor peak | PASS at OCV ≥ 3.4 V with Rint ≤ 0.8 Ω; FAIL at OCV 3.0 V or Rint ≥ 1.2 Ω | motor 0.37 A, cell 0.74 A at 3.4 V; VBAT 2.81 V |
| 1d Undervoltage lockout ≈ 3.4 V | PASS as designed | the boost UVLO is 1.8 V, so the 3.4 V threshold is firmware only |
| 2a TPS2553 current limit (ILIM 47 k) | PASS | 0.552 A |
| 2b FAULT timing | PASS | 7.49 ms after a short |
| 2c FAULT → latch clear → supply cut | PASS | latch and MOT_ALLOW low in < 1 µs; VMOT stays 0 V after the short is removed until a fresh ARM_CLK edge. Stall worst case (coil −10 %) = 0.407 A, no FAULT. |
| 2d TPL5010 timeout | PASS | PERM_L falls 0.2 µs after RSTn goes low and stays off after RSTn releases |
| 2e 3V3 collapses while VBAT/boost stay up | PASS | MOT_ALLOW < 0.66 V after 2.7 ms, boost EN off after 2.8 ms, also with SUP_PERMIT stuck high |
| 3 Enable logic | PASS 32/32 at DC and 32/32 through the whole chain | only docked + forward and undocked + reverse enable the motor; docked + reverse is blocked in hardware |
| 3 Single faults | **FAIL: one case (F1)**; WARN: four known or supervisor-covered cases | see findings |
| 3 Power-up, floating, brown-out | PASS, one WARN (F7) | VMOT 0 V in all ramps; dips to 0.5 / 1.0 / 1.5 V keep the motor off, dips to 1.8 / 2.2 V leave it running as designed |
| 4 DRV8835 full step at 26.5 Ω | PASS | 0.184 A per coil, supply peak 0.368 A, no upward spikes; the TPS2553 reverse-voltage trip never fires |

The case 3 WARN cases are: DOCK_N stuck low; MOT_FWD stuck low; R16 open with the line floating low; and a brown-out without reset. MOT_ALLOW reaches 0.74–0.82 V only in the worst-case model, where an undefined gate follows its rail below 0.8 V.

Case 1c: VBAT while the motor runs. The nRF VDDH minimum is 2.5 V.

| OCV \ Rint | 0.5 Ω | 0.8 Ω | 1.2 Ω | 1.6 Ω |
|---|---|---|---|---|
| 3.0 V | 2.60 | 2.26 | collapse | collapse |
| 3.4 V | 3.06 | 2.81 | 2.33 | collapse |
| 3.7 V | 3.39 | 3.17 | 2.81 | 2.15 |
| 4.2 V | 3.93 | 3.76 | 3.48 | 3.14 |

Case 1d: VBAT falls below 2.5 V at OCV 3.17 V for 0.8 Ω, at 3.50 V for 1.2 Ω and at 3.83 V for 1.6 Ω.

Case 4: at each step the supply current dips to about 0.01–0.1 A, then recovers with the coil's L/R time constant.

Not simulated: R55 open, and R91 open or short (the behavioural boost diverges with an open FB node). Analytically, R55 open runs the boost to its OVP of 5.5–6.0 V. The motor then either runs or trips FAULT, which is safe.

## Findings and fixes

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| F1 | medium-high (safety) | `DOCK_N` has no pull resistor; the hall is its only driver. If the hall joint opens and the line floats low, the gate reads "docked" and forward motion is enabled while undocked (VMOT 4.92 V in the simulation). | 100 k from `3V3` to `DOCK_N` (U4A.4, U33.1, U30.20, U1.B3). With it, an open hall gives VMOT 0 V. | passed to the board agent |
| F2 | medium | The droop margin depends on the unmeasured cell resistance. At Rint ≥ 1.2 Ω the 3.4 V rest lockout still lets VBAT fall below 2.5 V; at 1.6 Ω the supply collapses. | Measure the cell ESR. Firmware aborts when the loaded VBAT is below 2.8 V after the first step, and uses a 3.7 V rest threshold for a cold or aged cell. | firmware |
| F3 | low | The boost pre-charge draws about 1 A, so VBAT dips to 2.25 V at OCV 3.0 V with 0.8 Ω. | Start the boost only above 3.4 V OCV; add a second 10 µF on VBAT. | passed to the board agent / firmware |
| F4 | doc | INTERLOCK I.5 gives the ILIM range as 0.50–0.60 A; the datasheet gives 0.505 / 0.557 / 0.616 A. | Change it to 0.50–0.62 A. | passed to the board agent |
| F5 | low | The TPL5010 RSTn output is open-drain and needs a pull-up. | 100 k from `SUP_NRST` to `3V3`, unless the STM32C011 internal NRST pull-up is confirmed. | passed to the board agent |
| F6 | low | The DRV8835 VM pin has only the bulk capacitor; the datasheet asks for 0.1 µF at the pin. | 100 nF 0402 from `VMOT` to `GND` at U7.1. | passed to the board agent |
| F7 | low-medium | A 5 ms 3V3 dip without brown-out or TPL5010 reset does not clear a set latch in the model, so the motor resumes once firmware re-asserts permit. | Set the STM32C011 BOR to its highest level; hold `SUP_PERMIT` low for ≥ 10 ms after any reset. | firmware |
| F8 | info | The TPS2553 has no output discharge, so VMOT decays slowly (2.9 V at 120 ms). The DRV8835 is then unpowered or disabled, so nothing moves. | – | – |
| F9 | info | Known gaps: DOCK_N stuck low (INTERLOCK I.1a); MOT_FWD stuck low (covered only by the supervisor PHASE check, I.6); U32 stuck high leaves only the current limit, which holds a short at 0.552 A until the supervisor drops `SUP_PERMIT` about 2 ms after OC_OK falls. | – | – |
