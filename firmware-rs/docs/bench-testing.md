# Bench testing (gravimetric, WATER ONLY)

> **WATER ONLY. NEVER connect this to a body. NEVER fill it with insulin.** OpenPatch is a test project, not a medical device
> (`../../DISCLAIMER.md`). The core limits stay active during every bench run: max bolus, 15 U/h window, 1.5 U/min (1.7 U/min
> backstop), reservoir, dock gate, angle and current checks. The bench runner only paces pulses through the normal `Pump::bolus`.

## Building and flashing

```sh
scripts/build.sh --dev                     # bootloader + both apps (drive nfp-608-26-45-g15-12, angle-tmag; dev = dev-plaintext)
cd openpatch-bootloader && cargo run --release        # flash the bootloader first (probe-rs, SWD)
cd ../openpatch-bench && cargo run --release --features drive-nfp-608-26-45-g15-12,dev-plaintext   # bench board, RTT log
```

The application is linked at `0x9000` behind the bootloader: always flash the bootloader first. `cargo run` uses
`probe-rs run --chip nRF52840_xxAA` (`.cargo/config.toml`) and prints the defmt log (RTT). On a fresh E73 module the first boot writes
UICR PSELRESET and resets once (docs/boards.md). There is **no default drive**: always pass one `drive-*` feature (nfp-608-26-45-g15-12 (build.sh default), nfp-608-26-45-g1-1, syringe-rig-1ml, zwbpd006006-6-43, zwbpd006006-4-8, faulhaber-adm0620-16). DK: `--no-default-features --features board-nrf52840-dk,angle-tmag,drive-nfp-608-26-45-g15-12,dev-plaintext` (angle simulated). Without the pod's TMAG5273 use `angle-qdec-fallback` (docs/stubs.md: expect deviation faults).

`dev-plaintext` accepts plaintext frames and uses the public development session key. Without it the production stub refuses every
frame (docs/stubs.md); the bench service (below) works in both builds because it is not an OpenPatch frame, but it needs an
**encrypted BLE link** (button press -> bond).

## Starting a sequence

1. **Headless (compile-time defaults):** `OPENPATCH_BENCH_PULSES=10 OPENPATCH_BENCH_AMOUNT_MU=1000 OPENPATCH_BENCH_PAUSE_MS=30000
   OPENPATCH_BENCH_FILL_MU=50000 cargo run --release --features drive-nfp-608-26-45-g15-12,dev-plaintext,bench-autostart`. The sequence starts at boot as soon as
   DOCKED is asserted (`# waiting for DOCKED` until then). Amount: mU, multiple of 50 (0.05 U). Defaults 10 x 1.000 U, 30 s pause.
2. **BLE bench service** (all characteristics need an encrypted link: press the pod button, pair within 60 s):

   | | UUID | Properties | Payload |
   |---|---|---|---|
   | Service | `2E092A48-506C-477E-ADD4-448BF1490010` | | |
   | Control | `...1490011` | write / write without response | `op u8 (1 start, 2 abort)`, then for start `pulses u16`, `amount_mu u32`, `pause_ms u32`, little endian (11 bytes) |
   | Log | `...1490012` | notify | one ASCII line per notification, <= 100 bytes (CSV header, rows, `# ...` comments) |

   Example start of 10 pulses of 1 U with 30 s pause: `01 0A00 E8030000 30750000` (hex, little endian).
3. The pod button hold (>= 3 s) or the Abort op stops a running sequence (`Pump::emergency_stop` / `cancel_bolus`).

## Reading the output

Every line goes to RTT (`CSV ` prefix) and to the Log characteristic. Lines starting with `#` are comments (`# bench start`, `# waiting for
DOCKED`, `# bench done`, `# bench failed code=N`, `# rejected: ...`). The CSV is `openpatch_core::bench::CSV_HEADER`:

```
t_ms,pulse,cmd_mu,delivered_pulses,delivered_mu,angle_counts,faults
```

Extract the CSV from the probe-rs terminal log (timestamps and level are added by defmt):

```sh
cargo run --release --features drive-nfp-608-26-45-g15-12,dev-plaintext 2>&1 | tee run.log
grep ' CSV ' run.log | sed 's/.* CSV //' > bench.csv
```

With the default `DEFMT_LOG` (`.cargo/config.toml`) the HAL also logs one `DEBUG burst steps=.. peak_ma=.. samples=.. enc_counts=..` line per burst.
`delivered_pulses` (= motor steps) / `delivered_mu` are cumulative; `angle_counts` is the unwrapped leadscrew angle (4096 per turn) engine totals; `faults` is the core fault bitmask (protocol section 4.1).

## Gravimetric procedure

1. Water in the reservoir, outlet on a precision balance (0.1 mg), evaporation trap. Pod docked (DOCKED asserted), U100 model:
   **1 U = 10 ul**; water 0.998 mg/ul at 20 degC.
2. Tare. Start `N` pulses of `X` U (e.g. N = 10, X = 1 U, pause long enough to read the balance, or weigh once at the end).
3. After the last pulse wait for the drop to settle, weigh `m` (mg).
4. Per step volume: `ul_per_step = m / (0.998 x delivered_pulses)` with `delivered_pulses` of the last CSV row, `U_per_step = ul_per_step / 10`.
   **Nominal 0.006169 U/pulse (6169.1 uU = 0.617 ul) for the primary NFP G15/12 drive** (3 263 750 / 529 uU, 423.2 steps per screw turn); NFP coaxial G1/1: 0.004936 (2 611 000 / 529, 529 steps/turn); syringe rig: 0.001187 U (1.19 mU, 627 900 / 529); Zhaowei 6.43: 0.02030; Zhaowei 4.8: 0.02720; Faulhaber 16:1: 0.00816 U/pulse. The calibration is an exact rational in the core (`DriveCal`). Error = `U_per_step / nominal - 1`;
   target +/-5 % from 1 U. Also check `delivered_mu` against the commanded `cmd_mu` (exact remainder accumulation). `bench::prepare` now fills and PRIMES automatically (0.2 U of water through the connector); with the STRICT config `Resume` is refused (PrimeRequired 26) until a prime completed.
5. Repeat 50 times per amount for 0.05 / 0.5 / 5 U (docs/02-safety.md section 3). A systematic deviation is a mechanical finding
   (backlash, air, compliance): the calibration is a build-time preset with CRC and is not edited to hide it.

## Calibrating the occlusion current threshold (`limits::OCCLUSION_CURRENT_MA`)

The core input is `observe_motor_burst(steps, peak_ma)`: `OCCLUSION_CURRENT_BURSTS` (3) consecutive bursts above `OCCLUSION_CURRENT_MA`
(placeholder 140 mA) latch OCCLUSION. `peak_ma` is the peak of the SAADC scans of I_SENSE during the burst (RC filter 1.6 ms).

1. Run 10 free pulses (outlet open, water, no restriction): note the `peak_ma` values of the `burst` log lines (free running level).
2. Run pulses against a blocked outlet (clamped tube, water only): note the `peak_ma` values (stalled rotor, limited by the 105 mA phase current
   setting `MOT_REF` and the supply).
3. Choose a threshold between the maxima of (1) and the minima of (2) with margin; the threshold lives in `openpatch-core/src/limits.rs`
   (a core change, outside this crate; a runtime setter would be better, docs/architecture.md). Also check that the ripple of the
   chopper does not exceed it in (1).
4. Verify OCCLUSION latches (fault bit in the CSV `faults` column) before 2 U are undelivered.

## Angle channel check (replaces the old encoder calibration)

1. `angle_counts` in the CSV must advance by `4096 x pulses / (steps per turn)` (NFP G15/12: 423.2 steps per screw turn = 9.68 counts per pulse; coaxial G1/1: 529 steps, 7.74 counts). The core checks
   +-3 % per commanded leadscrew revolution and the 10 % window per >= 1 U: a deviation latches ENCODER_DEVIATION (fault bit in the `faults` column).
2. `# prepare failed code=...` or INTERNAL at the first tick with `TMAG5273 not found` in the log: the sensor does not answer (wiring, pod FFC without I2C, wrong address).
   `angle-qdec-fallback` makes the build runnable but is NOT sufficient for the 3 % check (docs/stubs.md).
3. `ANGLE_POLL_MS` (20 ms) and the half-turn unwrap limit are documented in `config.rs`; if the shaft can turn faster than 2048 counts per 20 ms the unwrap is wrong.

## Draw mode (refill the reservoir; WATER ONLY)

Draw pulls water INTO the reservoir by driving the leadscrew in reverse. Procedure:

1. Pump **suspended** (`Suspend` / fresh boot) and **UNDOCKED** (E73: remove the dock magnet from DRV5032; DK: BUTTON2 toggles the simulated DOCKED to off).
   Docked gives result `Docked` (27), not suspended `NotSuspended`, a latched fault or a missing angle sensor `Fault`.
2. Send protocol command 0x0F `FillDraw` with `FILL_MU` = volume in mU (`0` cancels). `Limit` if it does not fit (`capacity - remaining`), `Busy` while running.
3. Watch progress: Alert notifications (type 0x90: kind 1 progress, 3 done, 4 stalled, 2 fault) and `GetStatus` `DRAW_STATE` (1 drawing, 2 done, 3 stalled, 4 aborted),
   `DRAW_REQUESTED_MU`, `DRAW_DONE_MU`; flag `DRAWING`. Defmt shows each 500 step reverse chunk (`burst fwd=false`, peak current).
4. **Stall / end stop:** a chunk that executed short, < 50 % angle-confirmed reverse travel, or 3 chunks above the current threshold end the draw as STALLED
   (double beep); `DRAW_DONE_MU` is what the angle sensor confirmed (rear end stop reached or jam), the reservoir level is raised by exactly that.
5. A draw or fill sets `PRIME_REQUIRED` (flag bit 12): `Resume` is refused with `PrimeRequired` (26) until a prime completed (`FillPrime` prime sub-op, docked).
6. On the bench board the hardware interlock needs DOCKED for VMOT, so the draw cannot run there (docs/stubs.md, conflict 2): test draw on the DK or with a bench jumper on the DOCKED gate.

Weigh the water drawn from a tared source: drawn mass / 0.998 = ul, compare with `DRAW_DONE_MU / 10`.

## Syringe-rig procedure (NFP direct on a 1 ml U100 syringe plunger, WATER ONLY)

Build/flash on the DK: `cargo run --release --no-default-features --features board-nrf52840-dk,dock-simulated,angle-tmag,drive-syringe-rig-1ml,dev-plaintext`
(`scripts/build.sh` builds it as `rig`). DOCKED is simulated (initial docked, BUTTON2 toggles); the angle is simulated from the pulses unless the TMAG is wired.
1. Syringe with water, tip over a balance (0.1 mg), plunger on the motor leadscrew. **Barrel area 17.94 mm^2 is assumed: verify first** (1.19 mU = 0.119 ul per pulse):
   run 100 pulses, weigh, compute ul/pulse; if it differs, the preset is wrong, fix it in the core, do not trust volumes.
2. Delivery: as in the gravimetric procedure above (docked). Maximum 1 ml = 100 U; keep the fill within the syringe contents.
3. Draw (refill the syringe from a water source): BUTTON2 once = undocked, suspend, `FillDraw` mU; the plunger retracts, the angle confirms. Dock again (BUTTON2) and prime
   before delivery (`PrimeRequired`).
4. Never connect a body, never use insulin. The software DOCKED means the dock safety gate is NOT tested on this rig.

## Checks before each session

* DOCKED asserted, `# bench start ...` appears, no `faults` bits in the first row, buzzer silent.
* `defmt` shows `settings: ... calibration FirstBoot|Match` (Mismatch = the flash holds another drive than the build: no delivery, the record is not overwritten; erase the settings page to re-provision).
* Interlock (bench board): scope MCU_EN / ARM_CLK / VMOT around a pulse; kill the firmware (hold in debugger) and confirm VMOT drops within about 2 s
  (TPL5010). Never use a body.
