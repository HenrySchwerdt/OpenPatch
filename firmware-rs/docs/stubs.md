# Stubs, open points and what is NOT verified (`openpatch-bench`, bootloader)

## Syringe rig assumptions

`drive-syringe-rig-1ml` (id 0x30) assumes a barrel area of 17.94 mm^2 (627 900 / 529 uU = 1.19 mU per pulse): **VERIFY with a gravimetric run** before trusting any volume. Capacity is `CAPACITY_100` (100 U) as for all builds; the 1 ml U100 syringe holds 100 U. `CAL_UU_MIN` is now 1000 uU, the rig preset (1187 uU) is only slightly above it.

## Board / drive conflicts that need a hardware decision (read first)

1. **Angle sensor vs pod FFC.** The core's primary angle channel is the TMAG5273 over I2C (0x35, P0.26 / P0.06; `Hal::angle_read`, `None` = refuse to deliver).
   The current board documentation (`electronics/bench/pin-assignment.md`, rewritten for another drive concept) does not match the stepper pin map this firmware
   implements (the map in docs/boards.md was taken from the earlier stepper revision, unchanged by decision), and the pod FFC of that document may carry no
   I2C pins, so the TMAG may not be reachable. Without it the default build (`angle-tmag`) never delivers (`# prepare failed`, INTERNAL). Workaround for bench
   runs: cargo feature **`angle-qdec-fallback`** synthesizes angle counts from the two DRV5032 hall switches (quadrature, 1024 counts per edge, 1 pole pair
   placeholder = 4096 counts per turn only at 4 edges). It is **NOT sufficient for the 3 % per revolution check**: expect ENCODER_DEVIATION faults.
   On the DK the angle is simulated from the executed pulses (exact).
2. **Draw mode vs the hardware interlock: SOLVED IN FIRMWARE for the new gate, hardware change pending** (electronics agent, decision 2026-11-19): `VMOT = MCU_EN AND TPL5010_LATCH AND (DOCKED OR DIR_REVERSE)`. Firmware (`openpatch_core::interlock`, `hal/driver.rs`): a FillDraw (undocked + suspended, reverse only) calls `Hal::motor_enable_dir(Reverse)`, which sets DIR=reverse as the FIRST action of the power-up plan, before KILL_N / MCU_EN / ARM, then verifies LATCH_Q_MON and that VMOT came up; the driver wakes only after that. A forward step request while undocked (or a reverse step while docked) is refused, cuts the supply and is reported as `MotorFault::ForwardWhileUndocked` / `ReverseWhileDocked` (core latches INTERNAL); after any DIR change while powered and after every burst VMOT is compared with the gate model (missing = fault, present where the gate must be open = interlock failure latched, TPL5010 reset path). DIR returns to forward only after the supply is verified cut. The firmware still refuses a draw unless undocked + suspended and never bypasses the gate. Host-tested model + ordering: `openpatch-core/tests/interlock.rs`. **UNVERIFIED on hardware**, and valid only once the board really implements the new gate: on the OLD board (`VMOT on = latch AND MCU_EN AND DOCKED`) a draw still fails the VMOT check (NoSupply). Pin: MOT_DIR stays where `docs/boards.md` / `board/e73.rs` put it until `electronics/bench/pin-assignment.md` is synced (one-file change: `board/e73.rs`). OPEN datasheet question: STSPIN220 latches MODE4/DIR at the STBY edge; in a draw DIR is at the reverse level then (DS11633 could not be fetched in this session): confirm full step does not depend on MODE4. Historical text of the old limitation follows.

   *Old limitation:* (limitation for `board-bench-e73`; solved in firmware for the DK and the syringe rig). `VMOT on = latch AND MCU_EN AND DOCKED` (hardware), but `FillDraw` requires the pump UNDOCKED. On the bench board the
   motor supply therefore cannot come up during a draw: `motor_enable(true)` fails the VMOT check, the reverse burst returns 0 pulses and the draw ends STALLED/fault.
   The firmware does not bypass the interlock. Options (hardware): a bench jumper that forces the DOCKED gate (Q6) for draw tests, or a separate "draw"
   enable path. Draw works end to end on the **DK builds** (no interlock; BUTTON2 toggles the simulated DOCKED, so the pump can be undocked) including `drive-syringe-rig-1ml`. The safest minimal bench solution is exactly that: use the DK + rig for draw tests; a real fix on the controller board is hardware (a DRAW jumper forcing the DOCKED gate Q6 only while a draw is commanded, with the firmware still refusing it unless undocked + suspended). The firmware never bypasses the gate. Feature `dock-simulated` (software DOCKED, initial docked) is compile_error!ed with `board-bench-e73` unless `unsafe-bench-override` is also given, and even then the supply gate still needs the real DOCKED.
3. TMAG5273: register map, 13 bit angle decode, I2C address variants, CRC and mode configuration are now checked against datasheet SLYS045C (April 2026) and covered by host tests (`openpatch-core/tests/tmag5273.rs`, module `openpatch_core::tmag5273`). Fixed: the angle decode (the old code shifted the 13 bit value as if it were left aligned; the datasheet has D12..D0 right aligned in {MSB, LSB}, 9 bit integer degrees + 4 bit 1/16 degree fraction). Added: DEVICE_ID check, POR clear and POR/DIAG rejection, torn-read check via CONV_STATUS.SET_COUNT, optional CRC (`config::TMAG_CRC_EN`, off). Hardware verification is STILL OPEN (I2C on the FFC, first conversion, CRC coverage of the 4 byte read, magnet magnitude).


> TEST PROJECT, never to be worn. Read this before trusting any behaviour listed as "unverified".

## Not verified on hardware (biggest caveat)

Everything builds (`scripts/build.sh`), but **no code has run on a target**: no debug probe was available and the nRF52840 is not emulated by QEMU.
Unverified, in order of risk:

1. Step generation: PWM1 `Times(n)` playback, `PWMPERIODEND -> TIMER1 COUNT` counting (timer in `LowPowerCounter` mode), `LOOPSDONE -> STOP` self stop.
   Check with a logic analyser on STCK: exactly `n` pulses of 2.5 ms high at 200 Hz, none afterwards, counter == n.
2. Interlock sequence and its timing constants (`VMOT_SETTLE_MS`, `VMOT_ON_MIN_MV`, `VMOT_FALL_TIMEOUT_MS`, `STBY_WAKE_US`), the "supply not verified cut -> withhold DONE" path.
3. TPL5010 handshake: DONE is pulsed once per WAKE edge (`wake_task` flag), only after a tick verified the idle interlock. The exact TPL5010 DONE window relative to WAKE was
   taken from the pin table (`electronics/bench/pin-assignment.md`), not from its datasheet.
4. MPSL timeslot flash while a connection is active; worst-case CPU stall of the safety tick during a page erase (architecture.md says how to measure it).
5. SDC memory (16 KB reserved, estimate about 4 KB), LE Secure Connections pairing duration with pure Rust p256, bonding and `is_bonded_peer` with a resolvable private address.
6. QDEC with the DRV5032FA hall switches (20 Hz sampling), SAADC scan timing, TWIM probe of the TMAG5273.
7. UICR PSELRESET write + single reset on a fresh module.
8. Bootloader swap / revert / pending-update verification (only the signature scheme was cross-checked on the host: sigtool signature verified with `salty`).

## Implemented as a stub (`TODO(stub)` in the sources)

| Item | State |
|---|---|
| Application layer key agreement (`crypto.rs`, `ble/mod.rs`, `openpatch-proto::handshake`) | **Implemented** (protocol v1.1 section 5.2, `docs/04-protocol.md`): per-connection ephemeral X25519 + HKDF-SHA256 mixed with a long-term pairing secret `PS` (created by an application layer pairing handshake inside the button window, stored in flash record 6), explicit key confirmation, one AES-128-CCM key per direction + nonce salt. The BLE task runs the handshake (frame types 0x40..0x43), hands keys to the safety task through `SESSION_EVT`, which replaces the `Session` before it opens the next frame; the keys are erased when the link closes. A production connection starts without keys and refuses every non-handshake frame with AUTH until the phone has completed `SESSION_INIT`/`SESSION_FINISH`. Shared vectors: `docs/vectors/session-key-agreement.json` (Rust + Swift + Python). **Not hardware tested.** Open: pairing is trust-on-first-use unless an OOB code is configured (`Responder::set_oob`, not wired to any source), `PS` is stored unencrypted in flash (APPROTECT), the DRBG is seeded once per boot, no rate limit on INIT frames. Feature `dev-plaintext` (never default): fixed PUBLIC dev key + plaintext, unchanged; a phone that runs the handshake gets negotiated keys for that connection (plaintext still accepted), the dev session is restored when the link closes. |
| Pairing refusal outside the window | trouble-host 0.8.0 has no hook to reject an SMP pairing request. Enforced by: disconnecting unbonded peers outside the window (on connect and every 250 ms), `set_bondable(false)` outside the window (no bond is stored), `permissions(encrypted)` on all characteristics, one pairing per button press (window closes after the first bond), and the application layer CCM. A peer can briefly complete a non-bonded pairing in the race before the disconnect; it can then still not use any characteristic without the app key (production). |
| TMAG5273 | Implemented (`hal/tmag.rs`, `hal/angle.rs` unwrap, sampled every 20 ms during bursts); register map and decode verified against the datasheet only, UNVERIFIED on a device, possibly unreachable on the pod FFC (above). |
| DFU transport | Not implemented (out of scope): no BLE / file transport, no manifest writer in the app (`dfu::finalize` exists, is `allow(dead_code)`). Signing, manifest format, update state handling, trial-boot confirmation and bootloader verification are implemented. |
| Alert characteristic | Present (UUID ...0004, notify) and never written, as in protocol v1. |
| Hardware interlock on the DK | Absent by design (`interlock: None`); DOCKED and the angle are simulated. |

## Deliberate deviations / limits

* **LAST_SEQ persistence** is a write-ahead *ceiling* (`seq + 8` persisted before a frame is executed), not "every accepted seq" as in the Zephyr port.
  After a reboot `GetStatus.LAST_SEQ` reports `ceiling - 1`, which can be higher than the last really accepted seq (never lower). A phone that follows the
  "last known + 16" restart rule is unaffected. A command with `seq >= ceiling` waits (<= 500 ms) for the flash write and is refused if it does not complete.
* **Drive calibration mismatch** (flash holds another preset than the build, or a corrupt record): `None` is passed to `Pump::new` (NO_CALIBRATION latches, nothing delivers) and the record is never overwritten. The core would accept a stored record of another valid preset, so it is deliberately not passed through.
* **Test calibrations** (core feature `test-calibrations`, ids >= 0x7F00) must never be in a firmware build: `config::assert_no_test_calibrations()` checks `drive_cal::PRESETS` at startup and panics (watchdog reset).
* **Reverse (draw) bursts**: 600 Hz (hard cap 1000 pps by const assert), chunks <= 600 steps; the watchdog is serviced before every reverse chunk. Angle unwrap needs < half a turn between samples (20 ms sampling, margin >= 12x for every preset).
* **Reservoir model** after a power loss can only be lower than reality (stored with a 64 step margin), except for the window in which a burst larger than the
  remaining headroom completes before the flash write lands (one prime burst = up to 64 pulses = 0.25 U on the 16:20 drive).
* **Angle default**: `angle-tmag`. The QDEC (`coarse-qdec`, off by default) is only a coarse cross-check log; it is never the primary angle channel.

## Core API wishes

Done (see `architecture.md`): `Pump::set_occlusion_current_ma` (lowering only), `Hal::motor_fault` / `MotorFault`, `peak_ma` column in `bench::CsvRow`. The bench app does not expose the threshold setter over BLE / a build knob yet.
