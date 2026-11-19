# openpatch-sim: the virtual pod

> TEST PROJECT. Not a medical device, never to be worn (see `../../DISCLAIMER.md`).

Host-only crate. It runs the real `openpatch-core` on a physics model of the pod so that most of the
verification can happen before parts are ordered: delivery accuracy, occlusion detection, dock loss,
magnet loss, motor and watchdog faults, brown-out, flash power loss, comms loss, 48 h wear.

```
scenario (TOML / JSON) -> Runner -> Device -> Pump<SimHal> (openpatch-core, unchanged)
                                        |
                                      World: clock, battery, TPL5010, interlock, hall, TMAG5273, flash
                                        |
                                      Plant: stepper, gears, leadscrew, stick-slip plunger, reservoir,
                                             compliance, duckbill, occlusion, bubbles
```

| module | what |
|---|---|
| `params.rs` | every plant parameter, defaults from `spec/design-parameters.md` or a marked assumption; unknown scenario fields are rejected |
| `plant.rs` | step-by-step mechanics + hydraulics; a step is lost when the load torque exceeds the pull-out torque at that rate and supply |
| `electrical.rs` | battery, TMAG5273 sampling (13 bit -> 12 bit, noise, nonlinearity, magnet strength) and the 12 bit unwrap of `hal/angle.rs` |
| `flash.rs` | settings records with write latency and power-loss injection (A/B atomic or pessimistic) |
| `world.rs` | simulation clock, interlock gate `MCU_EN AND latch AND (DOCKED OR DIR_REVERSE)`, TPL5010, brown-out, `SimHal: Hal` |
| `device.rs` | boot + restore from flash, 1 s tick, persistence policy of `openpatch-bench`, a phone that talks the real protocol path |
| `scenario.rs`, `scenarios.rs`, `scenarios/*.toml` | scenario format and the built-in library (25 scenarios) |
| `runner.rs` | executes a scenario, writes the CSV time series and the JSON verdict |
| `montecarlo.rs` | N pods with manufacturing tolerances: accuracy and occlusion distributions |
| `report.rs` | `opsim report`: scenario table + Monte Carlo tables as markdown |
| `server.rs` | JSON-lines interface for end-to-end harnesses (below) |

Determinism: no wall clock, no OS randomness. A run is a pure function of (scenario, seed); the Monte
Carlo result does not depend on the thread count; changing the logging interval does not change the
physics.

## `opsim`

```sh
cargo run --release -p openpatch-sim --bin opsim -- list
cargo run --release -p openpatch-sim --bin opsim -- run wear_48h --csv wear.csv --json verdict.json
cargo run --release -p openpatch-sim --bin opsim -- run my_scenario.toml
cargo run --release -p openpatch-sim --bin opsim -- all --outdir /tmp/opsim
cargo run --release -p openpatch-sim --bin opsim -- mc accuracy --runs 1000 --seed 1
cargo run --release -p openpatch-sim --bin opsim -- mc occlusion-basal --runs 1000 [--axial-k 100]
cargo run --release -p openpatch-sim --bin opsim -- report --runs 1000 --out report.md
```

Exit code 1 = a verdict failed. CSV columns: `t_s, rate_mu_h, scheduled_mu, core_delivered_mu,
actual_out_mu` (what left the needle), `reservoir_model_mu, reservoir_actual_mu, plunger_mm,
pressure_kpa, angle_core, angle_true, current_ma, battery_mv, docked, faults, flags`.
The JSON verdict holds: delivered vs commanded in total, per bolus and per hour; fault log; per
injected fault the detection latency and the insulin undelivered at the alarm; the safety limit check
(commanded and at the needle); interlock check (forward motion while physically undocked); resets,
boot reports (what flash restored, reservoir model vs reality); draw results.

### Scenario file

```toml
name = "my_occlusion"
seed = 1
duration_s = 7200.0
events = [
  { at_s = 600.0,  action = "bolus", units = 2.0 },
  { at_s = 1800.0, action = "occlude" },
]
[setup]                      # standard bring-up: draw, dock, pair, activate, prime, resume
fill_u = 60.0
basal = [[0.0, 1.0]]         # (hour of day, U/h)
[params.fluid]               # any field of params.rs, defaults for the rest
bubble_ul = 10.0
```

`t = 0` is the end of the set-up. Actions: phone commands (`bolus`, `temp_basal`, `cancel_temp`,
`cancel_bolus`, `suspend`, `resume`, `set_basal`, `prime`, `draw`, `activate`, `release`,
`acknowledge`, `phone_connected`) and faults (`dock`, `charger`, `occlude`, `clear_occlusion`,
`bubble`, `magnet`, `angle_nack`, `phase_open`, `hall_stuck_docked`, `hang`, `kick_stuck`,
`brownout`, `battery_ocv`, `power_loss`, `flash_power_loss`, `force_steps`, `mark`). See
`scenario.rs` for the arguments.

## Plugging in the end-to-end harness (iOS `SimulatedPod`, diagnostics system)

`opsim serve --stdio` or `opsim serve --tcp 127.0.0.1:7878` is a JSON-lines interface to ONE live pod.
The simulation only advances when told to, so a test is fully deterministic and as fast as the host.

| request | effect |
|---|---|
| `{"cmd":"new","builtin":"wear_48h"}` / `{"cmd":"new","scenario":{...}}` | create the pod (runs the standard set-up unless `"standard_setup":false`) |
| `{"cmd":"run","seconds":60}` | advance simulated time |
| `{"cmd":"frame","hex":"..."}` | a protocol v1 frame (plaintext session) straight into `Pump::handle_frame`; the answer frame comes back as `response_hex` (`null` while the pod is off, booting or hung, like a lost BLE link) |
| `{"cmd":"inject","action":{"action":"occlude"}}` | any scenario action: phone-side commands (through the real frame path) and physical or electrical faults |
| `{"cmd":"status"}` | snapshot |
| `{"cmd":"verdict"}` | the running verdict |
| `{"cmd":"quit"}` | |

Every reply carries `ok`; `new`, `run`, `inject` and `status` add a `state` object with `pod` (the
decoded `GetStatus`: flags, fault names plus `new_fault_names` since the last snapshot, reservoir,
delivered, battery, bolus / temp state, draw state) and `plant` (the physical truth: fluid out of the
needle, real reservoir content, pressure, plunger position, lost steps, dock, buzzer).

How the two consumers use it:

* **iOS app / `OpenPatchCore` `SimulatedPod`**: implement the BLE transport as a TCP client. Encode
  commands with the existing Swift codec, send them as `frame`, decode the answers. Drive time with
  `run` from the test (`run 1` per tick of the app's clock). Use `inject` for the physical side:
  `{"action":"dock","on":false}`, `{"action":"occlude"}`, `{"action":"power_loss","duration_ms":50}`.
  The app then sees genuine pod behaviour (alarm bits in `GetStatus`, boot suspended, history ids)
  and the test can compare it with the plant truth in `state.plant`.
* **Diagnostics (`docs/06-diagnostics.md`)**: fault codes arrive as bits of `GetStatus.faults` today
  (`fault_names`, `new_fault_names` map them). When the diagnostics system introduces structured per
  component codes, add them to `runner::fault_names` / the `state.pod` object and as detectors in
  `scenario::Action::detector`; the injection side (`inject`) already covers the physical faults a
  component code would have to explain, so "inject X, expect code Y within T" becomes one scenario
  line plus an assertion. The physical truth in `state.plant` is the oracle for "was the diagnosis
  right".

The protocol session is plaintext (`Session<NoCrypto>`, `allow_plaintext`): the simulator stands in
for the `dev-plaintext` bench build. Encrypted sessions would plug in through the `Ccm` trait in
`device.rs`.

## Tests

```sh
cargo test -p openpatch-sim                                # scenarios, hardware models, physics, Monte Carlo
cargo test -p openpatch-sim --test findings -- --ignored   # open findings: fail by design
```

`tests/scenarios.rs` one test per scenario with the acceptance criterion of `spec/design-parameters.md`
section 7 / `docs/02-safety.md`; `tests/hardware.rs` the gate, watchdog, supply, sensor and flash
models; `tests/physics.rs` the plant against first principles (area, lead error, lost motion,
conservation of volume); `tests/montecarlo.rs` the distributions; `tests/findings.rs` the core bugs
and design gaps found with this simulator (`#[ignore]`d, failing, described in their doc comments).
