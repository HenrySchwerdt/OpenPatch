# Bench loop: Trio dosing against a real OpenPatch cup pod (water on a balance)

> **SAFETY. READ FIRST.**
> * OpenPatch is a **test project and not a medical device**. It must never be worn or used on a person.
> * The pod is filled with **water only**. Never insulin, never any other drug, not even "just for the bench".
> * The outlet goes into a **vial on a laboratory balance** through a capillary tube. Never connect it to a cannula, infusion set or body.
> * Nobody uses Trio's numbers for therapy during this test. Use a throw-away Trio build and a test profile, not your real settings.
> * See `DISCLAIMER.md` and `docs/02-safety.md`.

Goal: run Trio's dosing algorithm (oref) against a real pod and compare **grams of water delivered (balance)** with **units Trio reports as delivered**.

## 1. Units and balance requirements

U100 insulin, 1 U = 10 mm^3 = 10 ul (`spec/design-parameters.md`). Water at 20 C is 0.9982 g/ml, so **1 U = 9.982 mg** (about 100.18 U per gram). Density and temperature are parameters of the script (`--density`, `--temp-c`).

| Quantity | U | Water |
|---|---|---|
| One motor step (cup pod, 0.00703 U/step) | 0.00703 | 0.070 mg |
| Bolus granularity | 0.05 | 0.50 mg |
| Typical SMB | 0.1 - 0.5 | 1 - 5 mg |
| 2 U | 2.0 | 20 mg |

* Use a balance with **0.1 mg** readability (0.01 U). A 1 mg balance (0.1 U) works only for long runs; below 2 U of total delivery the script answers INCONCLUSIVE.
* **Evaporation** is the biggest slow error: 1 mg/min is already 0.1 U/min. Cover the vial (small opening for the capillary only) and float a thin oil layer on the water, or use a lidded weighing bottle. Measure the residual drift with a control vial for 30+ minutes and pass it as `--evaporation-mg-per-min`.
* **Tare drift and draughts:** warm up the balance, close the draught shield, keep the tube from touching the vial wall (surface tension and capillary pull add or remove grams).
* **Tare after the prime.** The prime pushes water through the path and is not a Trio dose. Start logging (or tare) only after the prime has finished and the first drop has left the capillary.
* Keep the capillary tip at a fixed height (outlet back-pressure changes with it) and below the water surface, or let drops fall freely, but do not change it during a run.

## 2. Hardware setup

1. Pod on the bench dock, outlet needle/port connected to a short capillary tube (PTFE, small bore).
2. Tube end into a vial on the balance, supported so the tube does not load the balance. Evaporation protection as above.
3. Balance connected to a computer (RS-232 or USB serial). Log `timestamp, mass_g` every 5-10 s with any serial logger (for example `pyserial`, `screen -L`, or the balance vendor's tool) and convert to the CSV below. Sync the computer clock (NTP) with the phone: a few seconds of offset only blur the per-bolus table.
4. Phone and computer both near the pod; Bluetooth range is not the thing being tested.

## 3. Software setup

1. Build Trio with OpenPatchKit following **`ios/INTEGRATION.md`** (not repeated here).
2. Pair the pod via Settings -> Devices -> Insulin Pump (Trio's own screens say "insulin"; read it as "water"; the OpenPatch screens say water). **Press the pod's button first**: it opens the 60 second pairing window in which the app creates the pairing secret (X25519 key agreement, stored in the iOS keychain of this phone only). From then on every connection runs a session handshake and all commands are AES-CCM encrypted; Settings -> OpenPatch -> Drive shows "Paired, encrypted session". A pod that was reset or paired by another phone needs its button again ("Pair again").
3. Fill the pod with **water**. The fill is an **assisted pressure fill**: with the pod OFF the dock, needle in the fill septum, tap Start filling; the pod retracts its plunger by itself at about 1.4 U per second and you push the water-filled syringe at the same pace until the bar is full. The cup pod has no check valve and **never draws by itself**: the app refuses any draw mode for it, and if you do not push, nothing enters. A stall or Stop keeps what was drawn; you can Fill more.
4. Dock the pod and tap Start priming. After a fill the pod first **takes up the lost motion of its drive** (about 2.5 U of plunger travel that delivers nothing, firmware `TAKEUP_MU_AFTER_DRAW`) over several prime commands, one slice per minute: the screen shows "Taking up the slack (n of 6)" and the prime takes several minutes. Only then does water reach the outlet.
5. Wait until the first drop has left the capillary, **tare the balance**, then start delivery. Check Settings -> OpenPatch -> Drive: preset `nfp-608-26-45-cup-miter-1-1`, id 0x26, 0.00703 U per step. Any other preset id is refused by the app (and 0x20-0x24 / 0x30 on purpose).

### CGM simulator (verified in the Trio checkout at `~/dev/Trio`)

Trio has a built-in **Glucose Simulator** (`Trio/Sources/APS/CGM/CGMType.swift`: `CGMType.simulator`; catalogue entry in `Trio/Sources/APS/Devices/DeviceCatalog.swift`, manufacturer group "Simulator"). Select it in **Settings -> Devices -> CGM**, pick Glucose Simulator in the device list (`Modules/Settings/SettingItems.swift`, `Modules/CGMSettings/View/CGMRootView.swift`).

What it generates (`Trio/Sources/APS/CGM/GlucoseSimulatorSource.swift`, class `OscillatingGenerator`): one reading every 300 s on a **sine wave** around a centre value, plus uniform noise, with a trend arrow derived from the slope. The UI (`Modules/CGMSettings/View/CustomCGMOptionsView.swift`) offers sliders for:

| Setting | Range | Default |
|---|---|---|
| Centre value | 80 - 200 mg/dL | 120 |
| Amplitude | 10 - 100 mg/dL | 45 |
| Period | 1 - 6 h | 3 h |
| Noise | 0 - 20 mg/dL | 5 |
| Produce Stale Values | on/off | off |
| Sensor Lifecycle Scenario | running, expiring, warmup, calibration, expired, failed | running normally |

Honest limitations:
* It is **not steerable beyond those sliders**: no meal, ramp, step or file-replay patterns.
* The trace is **not affected by insulin or carbs** (the app says so itself). Trio therefore keeps seeing the same glucose however much "insulin" the pod delivers, which is fine for a bench: dosing continues until max IOB or max basal limits stop it.
* A noise or amplitude slider value of 0 falls back to the default in the code (`getter ... != 0 ? ... : Defaults`), so noise cannot be switched off.
* Changes apply from the next reading (up to 5 minutes). On first start it back-fills 288 readings (one day).
* For repeatable stimulus use a high centre (for example 200 mg/dL, amplitude 10-30): Trio then continuously asks for temp basals and SMBs. For a deterministic replay a custom CGM or Nightscout-as-CGM feed would be needed; none is set up here and I did not test either.
* Trio also has a "Pump Simulator" (MockKit); do not use it, the point is the real pod.

### Trio settings for the bench run

| Setting | Where | Value |
|---|---|---|
| Dosing Mode | Settings -> Automated Insulin Delivery | **Closed Loop** (needs CGM and pump configured) |
| Max IOB | Settings -> Therapy -> Units and Limits | default is **0**, so no SMB happens; set e.g. 3 U |
| Max Basal | same | e.g. 2 U/h (temp basals above the profile basal) |
| Max Bolus | same | e.g. 3 U |
| Enable SMB Always | Settings -> Algorithm -> Super Micro Bolus (SMB) | on |
| Max SMB Basal Minutes | same | 30 (default) |
| Temp basal duration | none | fixed at 30 min in the algorithm code (`APS/OpenAPSSwift/DetermineBasal/DosingEngine.swift`); no setting found |

Any test profile works (for example basal 1.0 U/h, ISF 50, CR 10, target 100 mg/dL). Keep the profile identical across runs.

## 4. Run protocol

Start balance logging, then:

1. **Basal only, 2 h.** Closed loop off or glucose at target, profile basal running. Checks the steady rate and evaporation.
2. **Manual boluses** 0.5, 1 and 2 U, 10 minutes apart, 3 repeats each. Checks quantisation (0.05 U steps) and the per-bolus step.
3. **Closed loop with SMB and temp basals, 4-6 h**, simulator at a high centre value. Exercises direction reversals and small boluses.
4. **Comm loss and uncertain delivery.** Command a 0.5 U bolus and switch the phone's Bluetooth off at the same moment. Trio reports uncertain delivery (the pump manager maps a lost reply to `.uncertainDelivery`, `OpenPatchPumpManager+Commands.swift`). After Bluetooth returns the pump manager reads the pod again on its own (after 3, 10, 30, 60, 120, 300 s) and decides from the pod's own history: a `BolusStart` event proves the pod ran it (the dose is then reported to Trio, once), a completely read history without one proves it did not (nothing is reported), and an incompletely read history keeps the delivery uncertain. No second bolus is accepted until it is resolved. Record: what Trio showed, how it was resolved, and what the balance shows. The balance is the judge: a mismatch here is a finding, not noise.

Write down start time, balance model, evaporation rate, water temperature and pod serial for each run.

## 5. Where to read Trio's doses

Verified in the Trio code, there is **no CSV export of pump history**:
* **History tab** (`Modules/History/View/HistoryRootView+Treatments.swift`): lists boluses (SMB labelled "SMB"), temp basals with rate and duration, with timestamps. Read it by eye or screenshot it.
* **Settings -> Report a Problem -> Share Trio Logs** and **Settings -> Devices -> Insulin Pump -> Share Pump Logs** (`Logger/Export/LogExport.swift`): a zipped plain-text log (default 3 days in the report flow) with pump traces and algorithm lines. I did not verify that every dose appears there in a machine-friendly form.
* Settings export (`Modules/SettingsExport`) covers settings, not doses.

So `trio_doses.csv` is filled **by hand or by a small script** from the History tab or the logs. Core Data is on the phone and not reachable without extra tooling.

### `trio_doses.csv`

```
timestamp_iso8601,kind,units,duration_min,rate_u_per_h
2026-11-19T10:05:00Z,bolus,1.0,,
2026-11-19T10:15:00Z,smb,0.5,,
2026-11-19T10:00:00Z,temp_basal,,30,2.4
2026-11-19T10:10:00Z,suspend,,,
2026-11-19T10:30:00Z,resume,,,
```

`kind` is one of `bolus`, `smb`, `temp_basal`, `suspend`, `resume`. Bolus and SMB need `units`; temp basal needs `duration_min` and `rate_u_per_h` (a missing rate is derived from `units` / duration). Timestamps are ISO 8601; without an offset they are taken as UTC. Lines starting with `#` are ignored.

### `balance.csv`

```
timestamp_iso8601,mass_g
2026-11-19T10:00:00Z,25.0000
2026-11-19T10:00:30Z,25.0000
```

Readings in grams, at least every 10-30 s; the first reading is the default tare.

## 6. Compare script

`ios/tools/bench_compare.py`: Python 3.9+, standard library only.

```bash
cd ios/tools
python3 -I bench_compare.py --doses sample/trio_doses.csv --balance sample/balance_pass.csv
```

Options: `--density` (default 0.9982 g/ml) or `--temp-c` (Kell formula), `--tare-mass` (default first reading), `--evaporation-mg-per-min` (added back to the balance, default 0), `--window-min` (30), `--tolerance-pct` (5), `--min-units` (2.0), `--bolus-window-s` (120), `--json`. Exit code 0 PASS, 1 FAIL, 2 input error, 3 INCONCLUSIVE.

Rules: boluses and SMBs count exactly at their timestamp; a temp basal counts rate x duration, clipped to the next temp basal or suspend and to the end of the balance run; suspend cancels the running temp basal and doses while suspended are dropped with a warning (resume does not restart it). The per-bolus table subtracts the expected basal and needs a balance reading within the window; a bolus below 25 % of the reported size is flagged `NO CLEAR STEP`. Boluses larger than about 3 U take longer than 120 s at 1.5 U/min, raise `--bolus-window-s`.

Expected output for the passing sample (reported 4.900 U, balance 1.9 % low):

```
OpenPatch bench compare (WATER ONLY, test project)
Run        : 2026-11-19T10:00:00Z .. 2026-11-19T10:40:00Z (40.0 min, 81 balance readings)
Conversion : density 0.99820 g/ml -> 100.18 U/g (1 U = 10 ul = 9.982 mg)
Tare       : 25.0000 g, evaporation correction 0 mg/min

Totals
  Trio reported :     4.900 U
  Balance       :     4.809 U  (0.0480 g)
  Difference    :    -0.091 U  (-1.86 %)

Windows (30 min)
  start                 min   reported U  measured U     diff U    diff %
  2026-11-19T10:00:00Z   30.0       4.700       4.648     -0.052     -1.10
  2026-11-19T10:30:00Z   10.0       0.200       0.160     -0.040    -19.86

Boluses (step within 120 s)
  time                  kind   reported U  measured U   error %  status
  2026-11-19T10:05:00Z  bolus      1.000       0.982     -1.81  ok
  2026-11-19T10:15:00Z  smb        0.500       0.491     -1.79  ok
  2026-11-19T10:25:00Z  bolus      2.000       1.964     -1.82  ok

Verdict: PASS (abs error 1.86 % <= 5 %; tolerance 5 %, min 2 U)
```

The failing sample (balance 12.3 % low) ends with:

```
Totals
  Trio reported :     4.900 U
  Balance       :     4.298 U  (0.0429 g)
  Difference    :    -0.602 U  (-12.29 %)

Verdict: FAIL (abs error 12.29 % > 5 %; tolerance 5 %, min 2 U)
```

Run the tests with `cd ios/tools && python3 -I -m unittest`.

## 7. Interpreting the result

Expected error sources:
* **Step quantisation:** 0.00703 U/step, so a single 0.05 U bolus is 7 or 8 steps (0.049 or 0.056 U). The pod keeps the fraction of a step in its delivery accumulator and adds it to the next dose, so sums are exact within one step (0.007 U) while single SMBs are not; Trio is told the commanded 0.05 U. Compare sums and windows, not single SMBs.
* **Lost motion after a refill / reversal:** the firmware assumes 0.33 mm of play and takes it up before the first prime (`TAKEUP_MU_AFTER_DRAW` in `firmware-rs/openpatch-core/src/limits.rs`, about 2.5 U on the 74.6 mm^2 bore of the older pod). Open point: on the cup pod's 106 mm^2 bore the same 0.33 mm is about 3.5 U, so the firmware's reservoir bookkeeping may be about 1 U off after each fill. This loop measures it: weigh the water the first prime moves and compare with what the pod subtracts. The cup pod's real backlash is not measured yet.
* **Stick-slip** of the plunger seal: small boluses deliver late or in lumps; a window comparison hides it, the per-bolus table shows it.
* **Evaporation** (negative error growing with time) and **balance resolution** (noise on small doses).
* **Priming volume**: must be excluded by taring after the prime, otherwise the balance reads high.
* **Outlet back-pressure and tube compliance** delay the step; use a stiff short tube.
* **Trio's own estimate:** the pump manager reports bolus progress as linear at 1.5 U/min (`OpenPatchDose.swift`), so Trio's reported value is exact at the end of a dose, not during it.

A PASS means Trio's reported units match the water within the tolerance for that run, nothing more.

## 8. Results table (paste into `docs/STATUS.md`)

| Date | Run | Balance (resolution) | Evap. mg/min | Reported U | Measured U | Diff % | Verdict | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-MM-DD | basal 2 h | 0.1 mg | | | | | | |
| 2026-MM-DD | boluses 0.5/1/2 U | 0.1 mg | | | | | | per-bolus errors: |
| 2026-MM-DD | closed loop + SMB 4 h | 0.1 mg | | | | | | |
| 2026-MM-DD | BT loss at 0.5 U bolus | 0.1 mg | | | | n/a | n/a | uncertain shown: y/n; resolved as executed / not executed / stayed uncertain; balance agrees: y/n |
