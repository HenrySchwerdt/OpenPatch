# Firmware architecture (`openpatch-bench`)

> TEST PROJECT, never to be worn. Bench tests with WATER ONLY.

```
                         thread executor (lowest priority)                  P5 interrupt executor (SWI1)
 ┌────────────┐   FRAME_IN     ┌─────────────────────────┐                ┌───────────────────────────────┐
 │  BLE host  │ ─────────────▶ │                         │                │          SAFETY TASK          │
 │ + GATT     │ ◀───────────── │   (Channels, atomics:   │ ─────────────▶ │  owns Pump<BenchHal>:          │
 │ (trouble)  │   FRAME_OUT    │    src/shared.rs)       │                │  motor, interlock, STSPIN220,  │
 │ BENCH_CMD ─┼──────────────▶ │                         │ ◀───────────── │  TPL5010 DONE, ADC, STCK PWM   │
 │ CSV_OUT   ◀┼─────────────── │                         │   CSV_OUT      │  1 s Ticker: Pump::tick()      │
 └────────────┘                └─────────────────────────┘                │  then BenchRunner::step()      │
 ┌────────────┐   UI_CMD                                                  │  then persistence snapshots    │
 │ UI task    │ ─────────────────────────────────────────────────────────▶│                               │
 │ button/LED │ ◀──── atomics (ALARM_ON, BEEP_REQ, DELIVERING, ...)       └──────────────┬────────────────┘
 │ buzzer     │                                                                          │ PERSIST (try_send)
 └────────────┘      ┌──────────────┐  ┌──────────────┐  ┌───────────┐                   ▼
                     │ angle(QDEC) task │  │ wake task    │  │ DFU task  │          ┌──────────────────┐
                     │ QDEC -> atom │  │ WAKE -> flag │  │ mark_booted│         │ persistence task │──▶ MPSL timeslot flash
                     └──────────────┘  └──────────────┘  └───────────┘          │ (sole flash writer)│   (settings map)
                                                                                └──────────────────┘
```

## Ownership rules (the safety argument)

* `Pump`, the motor / interlock pins, the STSPIN220 pins, the PWM that makes STCK, the SAADC and the TPL5010 **DONE** pin belong to
  the safety task only (`hal::BenchHal` is moved into the `Pump`). `Hal::watchdog_kick` is called from `Pump::tick()`, which only
  the safety task calls, as the last action of a tick.
* The BLE task never touches the pump, motor, interlock or watchdog: it moves frames through `FRAME_IN` / `FRAME_OUT` and bench
  commands through `BENCH_CMD`. A hung or crashing BLE host cannot hold the motor on or feed the watchdog.
* The helper `wake_task` only sets a flag when the TPL5010 WAKE edge arrives; DONE is pulsed by the HAL only if that flag is set
  and the interlock verification of the tick passed. A stalled safety task therefore stops answering and the TPL5010 resets
  the MCU (and its RSTn clears the interlock latch in hardware).
* Flash is written only by the persistence task (and the DFU updater through the same mutex).

## Executors and interrupt priorities (`src/irqs.rs`)

| Priority | Users |
|---|---|
| P0 | radio stack: RADIO, TIMER0, RTC0 (set by MPSL) |
| P2 | embassy time driver (RTC1), GPIOTE |
| P3 | SAADC, QDEC, TWIM0, RNG |
| P4 | radio stack low priority (EGU0_SWI0, CLOCK_POWER) |
| P5 | **safety interrupt executor** (SWI1) |
| thread | BLE host, UI, persistence, encoder, DFU |

The safety task preempts the BLE host (a BLE burst can never delay a tick) and can block (a burst) without starving the
radio, because link layer timing lives in P0/P4. The application never uses P0/P1/P4.

## Safety task loop

`select4(Ticker 1 s, FRAME_IN, UI_CMD, BENCH_CMD)`:

* tick: `Pump::tick()` (DOCKED, wear, delivery engine, supervisor approval, motor burst, fault sync, **watchdog last**), then
  `BenchRunner::step()`, then persistence housekeeping and status flags (LED / alarm).
* frame: peek the seq (only frames that pass length + CRC + version may extend the ceiling), make the seq durable if needed,
  then `Pump::handle_frame(&mut Session<AesCcm>, ...)`, answer to `FRAME_OUT`.
* button: short press = `silence_alarm` (and pairing window in the UI task), hold 3 s = `Pump::emergency_stop` + bench abort.
* The bench runner runs inside this task, stepped after every tick, and starts doses through the normal `Pump::bolus`.

## Step generation and the burst (hardware timing)

`Hal::motor_step(Pulses)` (forward) and `motor_step_reverse(Pulses)` (draw, DIR reversed, 600 Hz, hard cap 1000 pps by a const assert) are short blocking calls. `hal/stepper.rs`:

* PWM1 plays a one-word sequence `n` times: each PWM period is one STCK pulse. **No CPU work per step.** The period is
  `1 MHz / STEP_RATE_HZ` ticks, 50 % duty (STCK high 2.5 ms, orders of magnitude above tSTCKH = 100 ns).
* PPI ch0: `PWMPERIODEND -> TIMER1 COUNT` (counter mode) = hardware count of produced periods. `motor_step` returns this count.
* PPI ch1: `LOOPSDONE -> PWM STOP`: the generator stops by itself after the last period, also if the CPU is stalled or hung
  (without it the PWM would keep repeating the last value).
* The CPU only busy-waits on the counter and samples I_SENSE (SAADC scan ~100 us) to track the peak motor current for
  `Hal::motor_current_peak_ma`. A timeout (`n / rate + 25 ms`) ends a failed burst; the count is reported honestly.

**Step rate trade-off** (`config::STEP_RATE_HZ`, default 200 Hz = 5 ms): a bolus tick needs 1 to 4 steps (a 1.5 U/min bolus is
3.4 steps/s), i.e. 5 to 20 ms of burst per second; only a prime (<= 64 steps) is long (320 ms at 200 Hz). Faster = shorter
blocking and less time with VMOT on, but less torque margin on the loaded geared drive (back-EMF) and more risk of lost steps;
slower = more margin and quieter, but a 64 step prime at 100 Hz blocks the executor for 640 ms. 150 to 250 Hz is the usable band
for this class of Ø6 mm geared stepper; verify lost-step behaviour on the bench (angle_counts column of the CSV).

The counter proves the PWM ran `n` periods; it cannot prove the STSPIN220 followed. That is the job of the **leadscrew angle sensor**
(TMAG5273, 4096 counts per turn, `Hal::angle_read`, cumulative, unwrapped in `hal/angle.rs`; `None` when the sensor does not answer = the core refuses to
deliver) and the motor current peak, which are separate inputs of the core supervisor (angle window + 3 %/turn check, current occlusion). The unwrap needs
< half a turn between two samples: bursts sample the angle every 20 ms, the shaft is at rest between bursts. The DRV5032 quadrature is not a primary channel any more:
feature `angle-qdec-fallback` synthesizes angle counts from it (insufficient for the 3 % check), `coarse-qdec` only logs it. On the DK the angle is simulated
from the executed pulses.

**Draw mode** (core `draw.rs`, protocol command 0x0F): runs from `Pump::tick()` in chunks of 500 reverse steps. The safety task is blocked for one chunk
(<= 0.85 s at 600 Hz); the HAL services the TPL5010 DONE before every reverse chunk, and ticks keep their 1 s cadence. Progress / done / stalled / fault
frames (type 0x90) are drained from `Pump::take_notification` after every tick and frame and notified on the Alert characteristic (docs/protocol-extensions.md).
On the bench board the supply gate lets a draw through only with DIR = reverse (`Hal::motor_enable_dir(Reverse)` sets it first, see the interlock section and docs/stubs.md).

## Hardware interlock sequence (`openpatch_core::bench_ctl`, bound to the pins by `hal/driver.rs`, bench board)

`MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H OR DIR_REV)` (`electronics/bench/INTERLOCK.md`; model, plan and every decision are in the core and host tested, `openpatch-core/tests/bench_ctl.rs`, `openpatch-sim/tests/post.rs`).
Each burst: `motor_enable_dir(dir)` = **DIR to the burst direction first** (it is an input of the gate), release `LATCH_CLR_N`, `MCU_EN` high, **one `ARM_CLK` rising edge immediately before delivering**, `LATCH_Q` must read high, `PGATE_MON` must show `MOT_ALLOW` and `VMOT_SENSE` the
supply, `OC_OK` must still be high, STBY high (hard-wired full step), EN/FAULT must release. Forward needs DOCKED, reverse (draw) needs UNDOCKED: a forward step while undocked is refused, cuts the supply and is a fault (`MotorFault::ForwardWhileUndocked`); after a DIR change while powered and after each burst
`VMOT_SENSE` and the gate readbacks are compared with the model (a leg that passes although its input is closed, a switch that blocks although all inputs are open, an over-current trip = driver fault). `motor_enable(false)` = STBY low, EN/FAULT driven low, then **one gate cuts in rotation**
(`MCU_EN` only / `LATCH_CLR_N` only / both), the collapse is verified, the second gate follows at once if it does not happen and the stuck leg is named. If the supply is **not verified cut** (or the latch / VMOT is active while the driver is off at the idle check of every tick) the controller latches `failed`: the DONE permit is
withdrawn, the alarm LED blinks and the TPL5010 resets the MCU within about 2 s (RSTn clears the latch independently of firmware). If the supply stays up while the P-FET gate is OFF (Q4 shorted) the controller is **quarantined** instead (no reset, STBY low, alarm, no power-up). Faults in the core
(`Pump::sync_faults`, `emergency_stop`) call `motor_enable(false)` too. The DK runs the same controller with `CtlCfg::NO_INTERLOCK` (direction, STBY, EN/FAULT only; every proof UNKNOWN).

**TPL5010 DONE** is answered by the EGU3 interrupt within microseconds of the WAKE edge, only inside the permit the safety task renews after every verified tick (`hal/wdt.rs`; the Rev A qualifier rejects any DONE edge outside the 20 ms WAKE window). `Hal::watchdog_kick` therefore means "verify the idle interlock and renew the permit".

**POST** (docs/boards.md): POST-S at boot (`BenchHal::boot_post_s`, findings reach the core through `Hal::take_diag`) and on `RunSelfTest`; POST-A (`GateCut`, `DockGateBlock`, `OverCurrentCut`) only while SUSPENDED, through `Hal::selftest`.

## Flash and the safety task

nRF52840 flash erase (about 85 ms per 4 KB page) and word writes stall the CPU, including interrupt entry, because code executes from
the same flash. Mitigations:

1. `nrf_sdc::mpsl::Flash` (MPSL timeslot API): the radio schedules erase/write between radio events, so connections survive.
2. Only the **persistence task** writes flash; the safety task only does `try_send` of small snapshots (the one exception, the
   seq ceiling, is awaited with a 500 ms bound before a command is executed).
3. Step timing is in hardware (PWM + PPI), so a stall during a burst cannot lengthen or shorten the pulse train; the watchdog interval
   (2 s) is far above the worst stall. Settings writes are coalesced (latest wins) and rare: seq ceiling every 8 commands,
   reservoir every ~48 steps, event ceiling every 64 events, pod state on change + every 5 min.

Measure on hardware: toggle a pin around `Settings::write` and check the worst-case tick jitter (not done yet).

## Persistence policy (`storage.rs`, `safety.rs`; protocol section 6.1)

| Record | Policy |
|---|---|
| seq | **ceiling** persisted before a frame with `seq >= ceiling` is executed (`new = seq + 8`); at boot `LAST_SEQ` is restored to `ceiling - 1`, so nothing accepted before a power loss can be replayed. Deviation from the Zephyr "write every accepted seq": strictly safer (write-ahead) and 8x fewer writes. The phone's "last known + 16" restart rule still works. |
| events | id ceiling, extended by 64 when fewer than 16 ids of headroom remain; extended immediately at boot (ids from the restored ceiling are not yet below the persisted one). |
| reservoir | fill mU + consumed pulses (draw raises the level in steps, so it is covered by the same snapshot), stored as `consumed + 64`, rewritten when `consumed + 16 >= stored`, so the model after a power loss can only be LOWER than reality (<= 64 pulses = 0.32 U per reset on the NFP drive). Tiny window: a prime burst larger than the headroom before the write lands. |
| drive cal | `DriveCal::to_bytes` (24 bytes, exact rational, magic + CRC) from `DriveCal::from_preset(<cargo feature preset>)` written on first boot, compared with the build at every boot; a mismatch is NEVER overwritten and passes `None` to `Pump::new` (core latches NO_CALIBRATION, no delivery, not acknowledgeable). No implicit drive: exactly one `drive-*` feature or `compile_error!`; startup asserts that the core has no test calibration (id >= 0x7F00). |
| pod | pair id, role, active, activation id, wear stored as an upper bound (`wear + 10 min`). The pod comes up suspended (core). |
| bonds | up to 2 BLE bonds (LTK, IRK, identity). |

`sequential-storage` (map) was chosen over `ekv`: no alloc, tiny, used by trouble's bonding example, works on any async `NorFlash`,
and the data set is a few small keyed records; `ekv` (LSM tree) pays off for many or large records.

## Security layers

1. BLE LE Secure Connections, Just Works, bonding only inside the 60 s button window; every characteristic `encrypted`.
2. Application layer AES-128-CCM (also for 0x90 notifications, nonce direction 2) (`openpatch_proto` feature `aes-ccm`), `allow_plaintext = false`. Keys come from the per-connection
   key agreement of protocol v1.1 section 5.2 (`docs/04-protocol.md`, `openpatch_proto::handshake`, run by the BLE task, keys handed to the
   safety task via `SESSION_EVT`): a production connection has no keys until the handshake completes and refuses everything else with AUTH;
   `crypto.rs` keeps the `SessionKeySource` seam. Feature `dev-plaintext` = fixed public development key + plaintext accepted. See docs/stubs.md.
3. Replay protection with persisted seq ceiling (above).

## Core API additions (formerly wishes)

* `SafetySupervisor::set_occlusion_current_ma` / `Pump::set_occlusion_current_ma`: runtime occlusion current threshold, starts at `limits::OCCLUSION_CURRENT_MA`
  (the hard limit) and can only be LOWERED (`Err(Limit)` above it or 0). Draw mode uses the same value.
* `Hal::motor_fault() -> Option<MotorFault>` (take-and-clear, default `None`) and `Hal::motor_enable_dir(MotorDir)` (default `motor_enable(true)`). The core
  queries the fault after every forward and reverse burst, latches INTERNAL and keeps the cause in `Pump::last_motor_fault()`; a draw is aborted.
* `bench::CsvRow::peak_ma` (`Option<u16>`, empty field without a current sensor), column `peak_ma` appended to `CSV_HEADER`; fed from `Pump::take_peak_ma()`.

## Diagnostics in the core (docs/06-diagnostics.md; WP-0, WP-1, WP-2 part 1, WP-4)

* **Crate `openpatch-diag`** (no_std, no unsafe): `DiagCode` (32 bit), `Severity`, `Action`, `Fru`, the 32 byte `DiagRecord`, `DiagSummary`, and the
  GENERATED `catalogue.rs` (150 rows, `codes::NAME` constants). Source of truth: `spec/diag-codes.csv`; `tools/gen_diag.py` generates the Rust and Swift
  catalogues and `docs/06-diagnostics-trace.md`; `tools/gen_diag.py --check` (also run by a cargo test) fails on drift against the doc tables.
* **`openpatch_core::diag::DiagState`** (about 3.4 KB RAM, owned by the `SafetySupervisor`): 64 record ring, active set (32), latched set (16), cause chain
  (depth 4), coalescing (10 s), escalation, clear records, notification queue, summary and FRU health (UNKNOWN until a proof exists). The legacy
  `Faults` bits are a **derived projection** of the active F/L records (`SafetySupervisor::faults()`); `latch(Faults::X)` raises a catalogue code
  (INTERNAL: `7-7C-003`). New call sites use `SafetySupervisor::raise` / `raise_caused_by`.
* **Hal (additive, default no-op):** `take_diag`, `motor_step_ex`, `interlock_state`, `selftest`, `reset_cause`, `breadcrumb`, `pod_uid`. The HAL reports,
  the core decides policy; HAL records are the root of the chain, the core's own record (for example `7-70-005`) links to them.
* **Detectors implemented so far** (one `diag_<code>` test each, see `tools/diag_coverage.py`): reset cause, tick overrun, battery low/critical, reservoir
  empty/low, wear warning/expired, calibration, limit vetoes, occlusion (shortfall, current), window and per-revolution deviation, carriage jam, lost angle
  channel, steps short of approval, HAL burst faults, draw aborted / blocked / direction inverted.
* **Deliberately not done in the core yet:** `7-7B-002 TICK_STALL` as a fault (the C reference only counts it; a fault bit would break the differential
  parity), frozen / jump / noise angle detectors and uncommanded-motion detection (need the nominal 72 h soak first), everything that needs the bench HAL
  (WP-3).
