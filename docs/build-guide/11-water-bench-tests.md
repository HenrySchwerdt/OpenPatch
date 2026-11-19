# 11. Water bench tests

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** Every test below runs on a table into a beaker, a vial or onto a balance. See [DISCLAIMER.md](../../DISCLAIMER.md) and [docs/02-safety.md](../02-safety.md) section 3.

The tests follow `docs/02-safety.md` section 3 (bench verification plan), spec §7 (safety limits) and the "bench tests that remain necessary" of `mechanical/sim/REPORT.md`. Run them **in this order**: each one gates the next. Record everything in the CSV templates of [templates/](templates/); the analysis helper is [tools/analyze_gravimetric.py](tools/analyze_gravimetric.py); the predictions to compare against are in [12-sim-predictions-and-report.md](12-sim-predictions-and-report.md).

| # | Test | Needs | Gate for |
|---|---|---|---|
| 11.1 | Baseline: empty stroke, free-run current, thrust | pod, controller, dummy head | everything |
| 11.2 | **Gravimetric accuracy 0.05 / 1 / 10 U** | balance 1 mg | 11.3 and later |
| 11.3 | **Occlusion** with a clamped outlet line | clamp, balance | |
| 11.4 | **Draw-mode refill** with water from a vial | controller revision with the DIR_REVERSE gate (confirm C3) | |
| 11.5 | **Leak tests** of the fluid path, anti-siphon | tissue, balance | |
| 11.6 | **Dock insert fit test** with the pod-less fixture and dummy head | fixture, dummy head, force gauge | |
| 11.7 | **72 h endurance** | everything | last |

## 11.0 Common setup

### Rules for every session

1. Read the warning box. Label the water WATER ONLY. **No insulin, no other drug, nothing from a medical supply** on the bench.
2. The firmware limits stay on (spec §7): max single bolus 10 U, **15 U per rolling hour**, 1.5 U/min (1.7 U/min backstop), occlusion at 2 U, encoder deviation above 10 % per 1 U. **They will pace you.** Plan the test day around them: the 10 U series of test 11.2b alone uses two thirds of the 15 U hourly allowance. Do not raise a limit and do not reset the clock to get around it.
3. Interlock: never jumper a gate. If the pod is "not docked" and you want it to deliver, dock it.
4. Controller on USB 5 V with the current limit set to 300 mA the first time of each session. Watch the motor and driver temperature by hand (stop if too hot to hold).

### Fill routes (choose one per test day)

**Route 1: manual fill through the septum (works on every controller revision).** Needs the carriage pre-positioned at assembly (6.2). 1) Pod undocked, outlet needle free; 2) 1 or 2.5 ml syringe with a blunt 27G needle through the fill septum (in the -Y wall hole); 3) tilt the pod so the outlet needle is the highest point and inject slowly: air leaves through the duckbill valve and the outlet needle until water appears at the tip; 4) fill the amount that matches the carriage position (50 U = 0.50 ml); 5) tell the firmware: headless `OPENPATCH_BENCH_FILL_MU=50000` books 50 U (the bench `prepare` also primes 0.2 U automatically), or the protocol command `FillPrime` sub-op 1 (Fill, `fill_mu`) from the dev build. **The firmware books the fill, it cannot see it:** a mismatch between water and booked fill only affects the end-stop and reservoir-empty logic, **not** the step-count accuracy test.

**Route 2: automatic draw (11.4).** Needs the DIR_REVERSE gate on the controller.

### Water, density and units

Use distilled or deionised water, degassed by standing 24 h in a loosely covered container at room temperature (reduces bubbles). Density of water, mg per microlitre (CRC values, rounded): 18 degC 0.9986, 20 degC 0.9982, 22 degC 0.9978, 24 degC 0.9973, 26 degC 0.9968. **1 U = 10 microlitres = 10 x density mg** (9.982 mg at 20 degC). Measure the water temperature with the thermometer before each series and write it into the log.

### Balance and set-up

1. Warm up the 0.001 g balance as the manual says; calibrate with the 10 g and 100 g weights; use the draft shield.
2. The **pod does not stand on the pan.** Fix it on the bench beside the balance (dock insert on the dummy head, tube hanging free).
3. Collection vial on the pan: a narrow vial with 2 ml of water, lid with a small hole for the tube. The tube end dips **2 to 3 mm below the water surface** and hangs from a stand with a slack loop so that the tube cannot pull on the pan. A hanging drop at the tube tip is an error: keep the tip submerged.
4. **Evaporation control:** an identical vial with lid and a dummy tube on the balance next to it. Measure its mass change over 10 minutes before each series: **drift rate in mg per minute** (negative = loss). Evaporation depends on your cover and the room; if it is more than **0.2 mg per minute** (4 % of a 5 U series in 7 minutes) improve the cover or add a 2 mm layer of mineral oil on the water.
5. **Resolution and uncertainty.** The balance reads to 1 mg. One weighing is uncertain by about 1 mg, a difference of two weighings by about **1.4 mg**. That is **14 % of a 1 U dose** (10 mg) and **280 % of a 0.05 U dose** (0.5 mg). **Therefore doses are never weighed one by one below 10 U:** you weigh a **series** and divide. The table gives the smallest meaningful series.

| Dose | One dose is | Series to weigh | Series mass | Uncertainty of the series |
|---|---|---|---|---|
| 0.05 U | 0.5 mg | **100 doses** (5 U) | 49.9 mg | +-2.8 % (200 doses, 10 U: +-1.4 %) |
| 1 U | 10 mg | **10 doses** (10 U) | 99.8 mg | +-1.4 % |
| 10 U | 100 mg | **one dose** | 99.8 mg | +-1.4 % |

6. **Settling:** after the last pulse wait **30 s** (pressure in the compliance relaxes, a drop forms and falls), then read the balance twice 10 s apart; use the second reading if both differ by 1 mg or less.

### Recording

Per test one CSV from the firmware (`bench.csv`, columns `t_ms,pulse,cmd_mu,delivered_pulses,delivered_mu,angle_counts,faults,peak_ma`) and one row in the corresponding template with the balance readings, temperature, drift rate and notes. Extract the firmware CSV as in `firmware-rs/docs/bench-testing.md`:

```sh
cargo run --release --features drive-nfp-608-26-45-g16-20,dev-plaintext 2>&1 | tee run.log
grep ' CSV ' run.log | sed 's/.* CSV //' > bench.csv
```

(`drive-...-g16-20` is the proposed 16:20 feature, see 10.4.1.)

## 11.1 Baseline: empty stroke, free-run current, thrust

Purpose: find out **before any weighing** whether the drive moves the plunger at all. This test uses the pod with water (route 1), dock closed, the tube end free over a beaker.

1. Prime (10.8) until water reaches the tube end.
2. Run **10 pulses of 0.05 U** then **10 pulses of 1 U** (the CSV `peak_ma` column holds the largest motor-current peak of each pulse). For each pulse the firmware must confirm angle counts of `4096 x steps / 661.25` (6.19 counts per step) within 3 % per revolution.
3. Record the free-running `peak_ma` of each pulse (median and maximum). The core threshold for an occlusion is **140 mA** (placeholder `OCCLUSION_CURRENT_MA`, three consecutive bursts). The simulation assumed 70 mA free, 175 mA stalled.
4. **Optional advanced thrust measurement:** with the lid off and the outlet clamped, place a compression force gauge or a load cell between the carriage nose and a rigid stop and command single steps. Read the peak force at current limits you can set on the controller (105, 150, 181 mA: **confirm C4**, motor limit 181 mA rated). The sim says **4.0 N at 105 mA (7.0 N at 181 mA)**. 5 motors if you have them (sim bench test 2).

| Criterion | Pass | Fail and action |
|---|---|---|
| Every pulse executed and angle confirmed | yes, `faults` = 0 | stall (angle does not advance, current high): the seal friction is above the thrust. Go back to 03.5, reduce friction, check the lid is not on the reservoir (8.1), check the gear mesh (6.3). **Do not continue** |
| Free-run peak current | well below 140 mA (margin of at least 20 mA) | above: too much friction or a jam (chapter 13) |
| `ENCODER_DEVIATION` bit | not set | wrong preset (10.4.1), sensor, magnet gap (7.2) |

## 11.2 Gravimetric accuracy: 0.05 U, 1 U and 10 U

Goal (docs/02-safety.md 3.1, spec §7): **within +-5 % of the commanded amount from 1 U.** The safety plan asks for 50 repetitions per amount; with the limits above the practical minimum is below. More series are better.

Prime, then for each series:

1. Tare the vial (or read it), note the temperature and the control drift rate, **start the firmware sequence** (10.7), wait 30 s after the last pulse, read the balance twice.
2. Write one row in `templates/gravimetric_log.csv`; **steps_total** is the `delivered_pulses` of the last CSV row.

| Series | Sequence parameters | Repeats | Time | Rolling-hour dose |
|---|---|---|---|---|
| **a. 0.05 U** | 100 pulses x 0.05 U (`amount_mu` 50), pause 2 s | 3 | 100 x (2 s + 2 s) = about 7 min each | 5 U |
| **b. 1 U** | 10 pulses x 1.000 U (`amount_mu` 1000), pause 5 s | 3, **with at least 1 h between series** (limit 15 U per hour) | 10 x 45 s = about 8 min each | 10 U |
| **c. 10 U** | one bolus of 10 U (`amount_mu` 10000), the maximum default; 1.5 U/min = **6.7 min** | 5, **one per hour or less** | about 7 min each | 10 U |
| **d. First dose after a draw** | after test 11.4: prime, then one 1 U dose, weigh (repeat after each draw) | 3 | | |

The result of the analysis tool for each series:

```sh
python3 docs/build-guide/tools/analyze_gravimetric.py my-gravimetric_log.csv
```

It computes: delivered volume `= (m_after - m_before - drift x elapsed) / density`, error against the commanded total, error against the step count (the mechanical accuracy: **does one step deliver 0.003951 U?**), measured U per step, the measurement uncertainty of the series, and for each dose class the mean, standard deviation, minimum, maximum and the fraction inside +-5 % and +-10 %.

### Acceptance criteria

| Quantity | Pass | Why |
|---|---|---|
| Mean error vs commanded, 1 U series and 10 U bolus | **within +-5 %** (spec §7, safety 3.1) | spec |
| Each individual 10 U bolus | within +-5 % | |
| 0.05 U, 100-dose series, cumulative | within +-5 % **of the series** (no per-dose claim: one 0.05 U dose is 12 to 13 steps and stick-slip delivers in lumps; the simulation shows single 0.05 U doses are inaccurate) | sim 2.8 |
| Measured U per step vs 0.003951 | within +-5 % | else a mechanical or preset error |
| Repeatability: standard deviation of the 1 U series means | at most **2.5 %** (the simulation's value) | sim MC |
| Series uncertainty smaller than the tolerance | required: if the uncertainty exceeds 5 % the series is **inconclusive**, not a pass | physics of the balance |
| Faults during the series | none | |

**Simulation to compare with** (Monte Carlo of 1000 pods, `openpatch-sim/REPORT.md` 5.1, 15:12 drive in the model): 1 U: mean -0.11 %, sd 2.47 %, 94.4 % within +-5 %; 10 U: mean +0.02 %, sd 0.79 %, 100 % within +-5 %; 0.05 U single doses: mean -0.18 %, **sd 50.7 %**; first 1 U after a refill and 0.3 U prime: **mean error -348 mU (-35 %)**, 5th to 95th percentile -725 to -83 mU. And `mechanical/sim/REPORT.md` 2.3: static error (area and lead) 1.4 % for 1 U; 2.4: **only 73.7 % of 1 U doses within +-5 %** with the tongue as drawn (the steel shim of this guide is the fix; S3 gives 7.1 % outside).

**Fail and action:** a systematic error (all series low or high by the same amount) points to a drive error (preset, gear pair wrong, A05 `4-41-002`), area error, or air in the reservoir; a large series scatter points to stick-slip (seal friction), backlash, or a loose gear. **Do not edit a calibration to hide the finding** (`firmware-rs/docs/bench-testing.md`): the result is a finding for the report.

## 11.3 Occlusion test (clamped outlet line)

Goal (spec §7, safety 3.2): **the occlusion alarm comes before 2 U are undelivered.** "Undelivered" = the units the pod booked after the blockage started minus the water that left the outlet since then.

Setup: the dummy head on the pod, **silicone tube from the barb to the collection vial**, a **hemostat or micro clamp** on the tube 5 cm from the barb that closes it **completely** (check with a syringe: no flow at all). Reservoir filled with at least 30 U, primed.

1. **Bolus occlusion.** Start an **8 U bolus** (1.5 U/min). **60 s after the start close the clamp** and note the time on a stopwatch. Wait for the alarm (the legacy fault bit `OCCLUSION` in the `faults` column, a log line, the alert; with WP-4, codes `5-53-001` shortfall or `5-53-002` current rise). Note the alarm time **t_alarm**.
2. Calculate: **commanded since clamp** = `delivered_mu` at the alarm minus at the clamp time (from the CSV); **water out since clamp** = vial mass change between the clamp and 60 s after the alarm / density (it is almost zero); **undelivered** = commanded since clamp - water out. **Pass: at most 2 U.**
3. **Release:** open the clamp, collect the water for 60 s: the stored volume (compliance, tube expansion) comes out. Record it. The pod must stay in the fault state (latched, needs `Acknowledge`).
4. **Basal occlusion** at **3 U/h** (the simulation's high-rate case): run a temp basal, clamp at 5 minutes, wait for the alarm (about 16 minutes after the clamp in the model). Repeat at **1 U/h** if you have the time: the model expects the alarm after **3019 s (50 min) with 0.83 U undelivered** at the nominal plant and **a 99th percentile of 7147 s (2 h) and 1.95 U**, and 9 of 888 simulated pods exceed 2 U.
5. **Peak-current calibration** (`firmware-rs/docs/bench-testing.md`): compare the `peak_ma` of the free pulses (11.1) with the `peak_ma` of the pulses against the clamp, and note the threshold of 140 mA against both. The threshold lives in `openpatch-core/src/limits.rs`; **record the numbers, do not edit the core to pass**.

| Criterion | Pass | Fail |
|---|---|---|
| Alarm raised | yes, before the bolus ends | no alarm: the current threshold is above the stalled current, or the encoder check is blind: report both peak currents |
| Undelivered at the alarm | <= 2 U | more than 2 U: report the commanded units, the compliance (clamped tube, air bubble) and whether the alarm was current or encoder based |
| Fault latched | yes, delivery stopped | motor still running: stop, unplug USB, chapter 13 |

**Simulation to compare with:** `mechanical/sim/REPORT.md` 5.4/5.5 predicts **FAIL** (3.4 to 3.9 U undelivered at the alarm with the 2 U threshold, because the stored volume of the compliance adds to it: set the firmware threshold to 0.1 U to meet 2 U); `openpatch-sim` (current rise plus encoder) predicts a bolus occlusion alarm **34 s after the clamp, 0.85 U undelivered**, a Monte Carlo mean latency of 103 s and a mean of 0.99 U undelivered (99th percentile 1.93 U), and for **encoder only** (no current sense) **50.8 % of bolus cases above 2 U**.

## 11.4 Draw-mode refill with water from a vial

Prerequisite: a controller revision with the **DIR_REVERSE gate** (confirm C3). Without it the firmware refuses (`Docked` 27) or the supply does not come up when undocked (`docs/stubs.md` conflict 2): mark the test **not possible on this revision** and use route 1. **Never jumper the dock gate.**

Setup: pod **undocked and suspended**, outlet needle free in air over a drip cup (the duckbill blocks air: the outlet needle may stay dry). A beaker or open vial of water on the balance with a **27G blunt needle** on a short tube, clamped so that its tip passes **through the fill septum** into the cap channel and stays in place; the needle tip under the water surface. (The simulation: a 29G fill needle at the 1000 pulses per second draw rate gives a suction of 29 kPa, just below the 30 kPa degassing limit, with a force margin that fails; 27G needs about 12 kPa.)

1. Read the water source mass (two readings). Note the carriage position.
2. Send protocol command **0x0F `FillDraw`** with `FILL_MU` = volume in mU (`0` cancels). **The BLE bench service has no draw op:** use the OpenPatchKit development build or any tool that sends protocol v1 frames (`docs/04-protocol.md`). Start with **20 U** (`FILL_MU` 20000), then 50 U.
3. Watch the alerts (type 0x90: 1 progress, 3 done, 4 stalled, 2 fault) and `GetStatus` `DRAW_STATE` (1 drawing, 2 done, 3 stalled, 4 aborted), `DRAW_REQUESTED_MU`, `DRAW_DONE_MU`. The motor retracts in chunks of 500 steps at up to 1000 pulses per second (the model: 3.95 U/s, about 25 s for 100 U).
4. After the draw: read the source mass again. **Drawn microlitres = mass loss / density; compare with `DRAW_DONE_MU / 10`.**
5. **Stall test:** request more than the free space (`capacity - remaining`): the draw must end `STALLED` at the rear stop with `DRAW_DONE_MU` equal to what the angle sensor confirmed; the level is raised by exactly that. (Model scenario `draw_endstop`: the pod believed 100 U, the housing stopped at 60 U; core 30.28 U, vial 30.04 U.)
6. A draw sets `PRIME_REQUIRED`: dock, prime (10.8) and run the **first 1 U dose** (11.2d).
7. Look through the clear reservoir for bubbles. Record the size of the largest bubble by eye (a 10 mm3 bubble is 1 U).

| Criterion | Pass | Fail |
|---|---|---|
| Drawn volume (angle confirmed) | at least 95 % of the requested volume when space is free | stall before the end stop: friction or current (11.1) |
| Source mass loss vs `DRAW_DONE_MU` | within +-5 % | air drawn in through the outlet (valve leak) or a leak at the septum |
| Draw stops by itself at the requested volume | yes | runaway: stop, unplug USB |
| Bubbles | none larger than about 10 mm3 | slow the draw (fewer pulses per second), larger fill needle, bleed with the prime |
| First 1 U after a draw | the model predicts **-22 to -60 %** without a backlash take-up | a large shortfall is expected: report it (firmware needs a take-up step) |

Model: `refill_draw` (50 U requested, core 49.91 U, vial 49.23 U) and Monte Carlo failed set-ups (112 of 1000 pods ended the draw in state 3).

## 11.5 Leak tests (what is and is not a leak test of this pod)

**Not applicable:** `docs/02-safety.md` 3.5 asks for "30 minutes under water at 1 m depth (IPX7-like)". The Rev A bench pod is **printed PA12 (porous) with an open FFC slot and no watertightness claim** (`mechanical/README.md`): **do not submerge it.** Report item 3.5 as "not applicable to the Rev A bench housing". What you can and should test is the **fluid path**.

1. **Static leak test (clamped outlet).** Fill, prime, clamp the tube. Put a tared blotting paper under the pod and around the end cap, the septum and the lid joint. Run **2 U** against the clamp so the pressure rises to the stall level (the current limit decides: sim 27 kPa at the 105 mA case), then **hold 10 minutes** (the compliance relaxes). Weigh the paper: **pass: no mass gain above 1 mg and no visible wet spot; fail: a wet spot at the septum, the cap spigot, the seal (water on the dry side of the plunger) or the lid.**
2. **Septum re-seal test:** 10 punctures with the 27G needle through the septum plug and out, then the static test again.
3. **Anti-siphon / free-flow test** (the duckbill and the self-locking screw, hazard H10): pod docked, filled, **not running**, the tube end 200 mm **below** the pod level in a vial on the balance for **30 minutes**. **Pass: no mass gain above 1 mg (0.1 U).** Then hold the tube end 200 mm **above**: no mass gain either. A mass gain means the duckbill leaks forward: record its cracking pressure by raising the tube end until flow starts (1 cm water is 0.1 kPa).
4. **Vacuum hold (after a draw):** after 11.4 leave the pod 30 minutes undocked: the carriage and `angle_counts` must not move (uncommanded motion `6-60-008` would latch); the reservoir model must not change.
5. **Splash only (optional):** 10 minutes of drops on the closed lid, then open it and look for water on the board. Report only; no pass claim.

## 11.6 Dock insert fit test (pod-less fixture and dummy head)

Do it once per insert batch and again after 50 cycles. You need the dock fixture, the 12 inserts, a dummy head and a force gauge or masses.

1. **Fit matrix**: as in 9.2 for all 12 inserts, in `templates/dock-fit-log.csv`: slides freely / snaps / rattles / insertion force (N) / pull-off force (N).
2. **Cycle test of the best insert: 50 dock and release cycles on the fixture**, force at cycles 1, 10, 25, 50, and look for **arm whitening, creep (the arms staying open), cracks, wear of the hook**. Prediction (sim 4.1 to 4.3): 1.5 % arm strain, pull-off 0.6 N, insertion 2.0 N.
3. **Needle landing:** pod docked on the dummy head, run **1 U** through the needle: water must appear at the tube end, **no leak at the plug**, repeat for all 12 inserts if the printed head allows. Sim 3.3/3.4: residual needle offset +-0.40 mm against a 1.34 mm usable radius, lead-in only 0.40 mm.
4. **Dock hall:** assert and release distances (10.5), and that `DOCKED` is true at **every** latched position and false at every unlatched one over 50 cycles. A chatter (more than 6 transitions in 10 s) is `2-21-003`.
5. **Acceptance (proposal; the simulation assumes 1.5 to 10 N):** insertion at most 2 N, pull-off 1.5 to 10 N, no rattle, no whitening after 50 cycles, `DOCKED` correct at every cycle, needle lands in every cycle.

## 11.7 72 h endurance

Last test, **unattended** but not forgotten: check the pod, the balance and the water at the intervals below.

1. **Plan**: a basal profile that exercises several rates, for example 5 segments between 0.5 and 1.5 U/h (average about 1 U/h, the model's `wear_48h` uses 5 segments plus 9 boluses of 0.05 to 6 U and two temp basals), a few boluses, and **BLE disconnects and reconnects**: every 6 h one disconnect of 5 minutes, and once a **35 minute** disconnect to see the 30-minute communication-loss fallback of a temp basal to the programmed rate. Fill 100 U (OP-100): 72 h x 1 U/h plus boluses stays under the capacity.
2. **Wear timer:** the firmware warns at **44 h** (`B-B1-001`) and stops delivery at **52 h** (`WEAR_MAX`, `WEAR_EXPIRED` = `B-B1-002`; spec §1b). The catalogue says the stop is **cleared by `Activate`**, which is what a pod swap does in the real two-pod system: run the first window to about 48 h, then `Release` and `Activate` (one pod standing in for the swap) and continue to 72 h. **Verify on your build** that `Activate` restarts the wear timer and that the reservoir model and the delivered totals are carried correctly; if it does not, report 52 h as the achieved endurance. Do not edit the limit.
3. **Collection:** the tube into a covered vial (small hole) with an identical covered **control vial** beside it; weigh both at 0 h and then **every 12 h** (30 seconds each), plus at the end. Corrected output = vial change - control change.
4. **Log**: the firmware CSV continuously (RTT log to a file, or the BLE Log characteristic), **room temperature every 30 minutes** (logger or by hand), and a note for every disconnect, reconnect, reset or alert.
5. **Pass criteria** (proposal from the spec): total delivered within **+-5 %** of the programmed total; no latched fault; no unplanned reset (the watchdog reset count stays 0); the comms-loss fallback happens after 30 min; no leak (paper test of 11.5.1 at the end, the paper under the pod during the test); the motor and driver do not overheat (hand test every check); the leadscrew angle channel stays within 3 % per turn over the whole run.
6. **Model:** `wear_48h`: core 79.12 U, needle 78.80 U (-0.4 %), max 60 min 6.93 U; `comms_loss_temp`: fall-back after 30 min; the first hour carries about 0.4 U of lost motion after a refill.

## 11.8 Stop and report

Whatever happens, write it down. A stall, a leak, an alarm that did not come: **these are results**. Fill in the report template ([templates/test-report-template.md](templates/test-report-template.md)) and send it (or open an issue) with the CSV files.

Next: [12-sim-predictions-and-report.md](12-sim-predictions-and-report.md).
