# Differential testing: Rust core vs the C reference

> TEST PROJECT, never to be worn. The crate `differential-tests` is host-only. It is the only place in `firmware-rs` that may use `unsafe` (FFI);
> the firmware crates stay `forbid(unsafe_code)`.

The Rust core (`openpatch-core`, `openpatch-proto`) is a port of the C reference (`firmware/core`). Both are driven by identical inputs and compared. The
C sources are compiled by `build.rs` (`cc` crate, `-std=c11`) together with a small shim, **`differential-tests/csrc/shim.c`**, that provides a heap-allocated
C pump, a C mock HAL (a port of `firmware/tests/mock_hal.c`: `steps_limit`, `delivered_pct`, docked, charger, battery, time) and a flat C ABI. Nothing under
`firmware/` is modified.

## How to run

```sh
cd firmware-rs
cargo test -p differential-tests                          # everything, ~5 s
cargo test -p differential-tests --test long_run -- --nocapture   # prints ops, response kinds, faults, events
DIFF_SOAK=40 DIFF_SEED_BASE=777000 cargo test -p differential-tests --test long_run -- --nocapture   # local soak (13 M ops, ~12 s)
```

On a divergence the pump tests shrink the failing operation list (delta debugging) and print a minimal, replayable reproducer (explicit frame bytes, tick
lengths and environment changes). The proptest runs do not persist regression files; the seed is printed in the failure message
(`check_seed(seed, n, ..)` in `src/harness.rs` replays it).

The crate enables the host-only calibrations: `openpatch-core = { features = ["test-calibrations"] }` (`DriveId::Test26100` 0x7F01 = 26 100 uU/step and
`Test8156` 0x7F02 = 8 156 uU/step; 16 steps/rev x ratio 16 = 256 steps/turn = exactly 16 angle counts/step = the C encoder's 16 substeps). They correspond
to the C presets 1 (26 100 uU, ratio 500) and 2 (8 156 uU, ratio 1600).

## What is covered

| Test file | Content | Volume |
|---|---|---|
| `tests/codec.rs` (A) | CRC-16, frame encode/decode, `op_session_open` + `op_cmd_decode` vs Rust `Session::open` + `decode_command` on random byte strings, TLV soup inside valid frames, mutated valid frames (bit flips, truncation, CRC repaired or not), persistent sessions (replay, seq 0xFFFE/0xFFFF, response/encrypted flags). Same accept/reject, same error code, identical decoded fields. Random commands encoded by Rust decoded by C and vice versa; byte-identical encodings (incl. `TooLarge` on small buffers). Responses: byte-identical for status-less answers and histories; with a status the Rust bytes minus tags 0x21..0x23 are byte-identical; Rust decodes C's bytes. | 8 proptests x 1 024 cases (each case 12..60 inputs) |
| `tests/engine.rs` (B) | `op_de_*` vs `DeliveryEngine`: random schedules (valid and invalid), temp basal, bolus, suspend/resume, comm heartbeat, time of day, ticks of 0 ms .. 200 000 s (slot edges, temp end, comm-loss edge, midnight wrap), full/partial/over-reporting commits. After every op: steps per tick, accumulator, scheduled/delivered mU, events, remaining bolus/temp, counters, schedule, return codes. Calibrations 26 100, 8 156, arbitrary 4 000..60 000 uU and 0 (uncalibrated). | 1 024 cases x 300 ops + 120 000 ops deterministic + 1-day flat-rate exactness |
| `tests/reservoir_log.rs` (C) | `op_res_*` vs `Reservoir` (fill, low threshold, consume incl. saturation, empty/low, capacities, uU 0..70 000); `op_log_*` vs `EventLog` (ring, 128 entries, restored ids incl. 0 and values around `u32::MAX`, reads from arbitrary ids). | 1 024 cases each + 180 000 ops deterministic |
| `tests/pump.rs` (D) | Whole pump, random operation streams compared after EVERY op (see below). | 768 cases x 400 ops |
| `tests/long_run.rs` (D) | Same generator, deterministic xorshift seeds, **325 000 ops** (400 seeds, every 8th is 3 000 ops long) with statistics at the end. | 325 000 ops |
| `tests/scenarios.rs` (D) | Scripted corner cases the random streams reach rarely: temp basal completion, comm-loss fallback (30 min), hourly cap (veto + `LIMIT_EXCEEDED`), occlusion / encoder deviation, INTERNAL (motor executes less than approved), reservoir empty, wear warning / expiry / re-activation / `restore_pod`, dock + charger + battery interplay, uncalibrated pump. Each scenario asserts that the expected event/fault really happened. | 10 scenarios x 2 calibrations |
| `tests/documented_differences.rs` | Pins every intentional difference (below) in both directions. | 4 tests |

The tests also check that the harness is not vacuous (generator corpora must contain accepted and rejected inputs; a deliberate mutation of the shim or of the
Rust calibration was confirmed to fail the suites, and the minimiser reduced it to a 4-operation reproducer).

### Whole pump (D)

Both pumps get the same operation: a command **frame** (plaintext sessions on both sides; types 0x01..0x0E with valid and invalid arguments: pairing, activate,
release, fill, prime, acknowledge, history, bolus, temp, schedule ...; mutated/garbage frames; replays and out-of-range sequence numbers; time-of-day tag),
`tick` (1 s granularity, odd lengths, stalls > 5 s, jumps of minutes, hours and 40..60 h for the wear limit), clock advance without tick, dock/undock, charger,
battery (3 000..4 100 mV), actuator health (`delivered_pct`), `steps_limit`, new session, `restore_pod`. The generator is state aware (paired -> filled ->
activated -> primed -> resumed) and has three phases (mixed / fast 5 s ticks / quiet) so the pump really delivers, drains the reservoir, completes temp
basals and loses comm. Random setups: both calibrations, capacities 70/100/200 U, restored next-event id (0, 1, random, near the top of `u32`) and 3 % of runs
with no calibration at all.

After every operation the harness compares:

* the response: both drop with the same error code, or both answer with the same type/flags/seq and TLV list (byte-identical frame for status-less answers);
* faults, buzzer pattern, total motor steps, `motor_enable` call count and state, watchdog kicks, angle/encoder position, **"never stepped while disabled"** on both;
* delivery engine (suspended, temp/bolus state and remaining, time of day, comm timer, accumulator, scheduled scaled units, requested/delivered/dropped/pending steps,
  schedule), reservoir (fill, consumed, remaining), pod state (pair, role, active, activation id, wear, dock, pending temp, last release), supervisor (commanded
  counts, last/base encoder, docked/active/wear-expired, battery-low, max steps/min), tick overruns;
* a direct `GetStatus` of both pumps (decoded fields, see normalisation) in addition to the status carried by responses;
* every new event-log entry field by field (id, time_s, type, a, b), next/oldest id.

Statistics of the committed long run (`-- --nocapture`): 325 000 ops, ~66 000 frames, ~190 distinct (command type, result) response kinds, fault bits
occlusion / encoder deviation / reservoir empty / battery critical / INTERNAL / no calibration / wear all seen (the hourly `LIMIT_EXCEEDED` fault is covered by
the scenario test and by soak runs), event types 1..5, 7..24 seen (TEMP_DONE 6 by the scenario test).

## Result

No real divergence between the Rust core and the C reference was found in any compared quantity (including 13 M ops of soak). The only differences are the
documented intentional ones below. Harness artefacts that were found and fixed during development: C keeps stale pending-temp rate/minutes after use (Rust clears
the `Option`, not observable, normalised); `op_log_read` and the Rust read both return nothing once ids have wrapped past `u32::MAX` (identical, but it made the
event comparison in the pump runs impossible, so the pump runs start at most 2 M below the wrap; the wrap itself is compared in `reservoir_log.rs`).

## Intentional differences and how the harness treats them

| # | Difference | Treatment |
|---|---|---|
| 1 | `DRIVE_CAL` status bytes: C preset ids 1/2, 20 steps/rev, ratio 500/1600; Rust test calibrations 0x7F01/0x7F02, 16 steps/rev, ratio 1600 | only the uU/step floor (identical) is compared; the other three fields are pinned to differ |
| 2 | Rust: status tags 0x21..0x23 (draw state/requested/done), `FW_VERSION` 0x0200 (C 0x0100), flags bits 11/12 (`DRAWING`, `PRIME_REQUIRED`) | tags/bits removed before comparing, then everything else is byte-identical; the Rust side uses `PumpConfig::RELAXED` (no mandatory prime) so bit 12 never appears anyway |
| 3 | Rust command 0x0F `AssistedFill`, error codes 26 (`PrimeRequired`) and 27 (`Docked`); C answers 0x0F with UNSUPPORTED (9) | never generated in shared streams (a mutated frame whose type byte becomes 0x0F is rewritten to GetStatus); pinned on both sides in `documented_differences.rs`; Rust-only behaviour covered by the `openpatch-core` tests |
| 4 | Rust per-leadscrew-revolution angle check (4096 counts +-3 % per commanded revolution) and motor-current occlusion (disabled: the mock returns `None`) | knob `delivered_pct` restricted to {100, 100, 100, 50, 0}; once degraded it stays until an encoder/occlusion fault tripped, so C's 10 %/1 U window fires as well. A short degraded episode (or a window misaligned with the revolution) can still trip only the Rust check (e.g. a 5 % shortfall: C tolerates 10 %, Rust faults after one revolution, pinned in `documented_differences.rs`). When that happens the run **stops** at that operation (counted as `documented_rev_stops`; everything before was compared strictly): 0 of 400 seeds in the committed run, 5 of 16 000 in the soak. |
| 5 | Pending-temp rate/minutes remain stale in C after use; Rust clears them | compared only while `pending_temp` is set |

Engine and event-log values the Rust type does not expose (`bolus_remaining_scaled`, `temp_remaining_ms`) are compared as the rounded-up public values (mU /
minutes); their exact values are still verified indirectly through the step counts, events and the accumulator on every tick.

## What is intentionally NOT covered by differential tests

* **Production presets** (`Nfp608_26_45`, `Zwbpd006006_*`, `FaulhaberAdm0620_16` with non-integer uU/step as an exact rational): the C core does not know them and
  `op_drive_cal_validate` accepts only records equal to its two presets (magic + CRC + preset equality), so a C calibration with arbitrary uU cannot be built
  by the shim. Rust-only coverage: `openpatch-core/tests/{presets,calibration}.rs`. (The engine and reservoir comparisons *do* use arbitrary integer uU values because
  those modules take a plain number.)
* SMA / ratchet drive code, draw mode (`AssistedFill` and the reverse motor path), the per-revolution check and motor-current occlusion, the mandatory
  prime after fill (`PumpConfig::STRICT`), notifications (frame type 0x90), `emergency_stop`, `silence_alarm`: Rust-only features, covered by `openpatch-core` tests.
* AES-CCM / encrypted sessions (the C core only has a hook; both sides run plaintext sessions here; an encrypted frame is dropped with AUTH by both).
* Sensor-missing behaviour (`angle_read() == None`) and a motor-current sensor: the mock always provides an angle and never a current.
* Persistence of pod state / event ids across reboots beyond `restore_pod` and a restored next-event id.
* The bench/bootloader crates and everything hardware related.

## Layout

```
differential-tests/
  build.rs            builds ../../firmware/core/src/*.c + csrc/shim.c with the `cc` crate
  csrc/shim.{h,c}     flat C ABI, mock HAL, snapshot layouts (documented at the top of shim.c)
  src/ffi.rs          unsafe FFI wrappers (SAFETY comments), RAII handles
  src/rmock.rs        Rust mock HAL with the C mock's semantics
  src/desc.rs         codec independent command/response description, flat conversions
  src/pair.rs         C pump + Rust pump side by side, per-op comparison, normalisation, minimiser
  src/gen.rs          state-aware reproducible operation generator (xorshift)
  src/harness.rs      run a seed, shrink, report
  tests/*.rs          see the table above
```
