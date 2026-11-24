# Stubs, open points and what is NOT verified (`openpatch-bench`, bootloader)

## Syringe rig assumptions

`drive-syringe-rig-1ml` (id 0x30) assumes a barrel area of 17.94 mm^2 (627 900 / 529 uU = 1.19 mU per pulse): **VERIFY with a gravimetric run** before trusting any volume. Capacity is `CAPACITY_100` (100 U) as for all builds; the 1 ml U100 syringe holds 100 U. `CAL_UU_MIN` is now 1000 uU, the rig preset (1187 uU) is only slightly above it.

## Board / drive conflicts that need a hardware decision (read first)

1. **Angle sensor vs pod FFC: RESOLVED by the Rev A board.** `electronics/bench/pin-assignment.md` (Rev A, stepper) is now the single source of truth and matches this firmware: the 10 pin FFC carries `I2C_SDA` / `I2C_SCL` (pins 3 / 4) to the TMAG5273 (0x35), `3V3`, `DOCK_N`, the optional `HALL_A/B`
   and the `POD_ID_N` loopback; FFC presence is read back (`POD_ID_N`, TMAG ACK; `3-30-001`). The text below is the history. The TMAG5273 itself is still UNVERIFIED on hardware (plane, range, I2C on the FFC). Without it the default build (`angle-tmag`) never delivers (`# prepare failed`, INTERNAL). Workaround for bench
   runs: cargo feature **`angle-qdec-fallback`** synthesizes angle counts from the two DRV5032 hall switches (quadrature, 1024 counts per edge, 1 pole pair
   placeholder = 4096 counts per turn only at 4 edges). It is **NOT sufficient for the 3 % per revolution check**: expect ENCODER_DEVIATION faults.
   On the DK the angle is simulated from the executed pulses (exact).
2. **Draw mode vs the hardware interlock: SOLVED in firmware AND on the Rev A board** (`INTERLOCK.md`): `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H XOR DIR_REV)`; `DIR_REV` is the `MOT_DIR` net itself (R96). The paragraph below is the firmware design, now in `openpatch_core::bench_ctl`; the OPEN datasheet question about DIR at the STBY edge is CLOSED: MODE1 = MODE2 = low forces full step whatever DIR / STCK are (DS11633 6.2, Table 8). Old text: `VMOT = MCU_EN AND TPL5010_LATCH AND (DOCKED XOR DIR_REVERSE)`. Firmware (`openpatch_core::interlock`, `hal/driver.rs`): a AssistedFill (undocked + suspended, reverse only) calls `Hal::motor_enable_dir(Reverse)`, which sets DIR=reverse as the FIRST action of the power-up plan, before KILL_N / MCU_EN / ARM, then verifies LATCH_Q_MON and that VMOT came up; the driver wakes only after that. A forward step request while undocked (or a reverse step while docked) is refused, cuts the supply and is reported as `MotorFault::ForwardWhileUndocked` / `ReverseWhileDocked` (core latches INTERNAL); after any DIR change while powered and after every burst VMOT is compared with the gate model (missing = fault, present where the gate must be open = interlock failure latched, TPL5010 reset path). DIR returns to forward only after the supply is verified cut. The firmware still refuses a draw unless undocked + suspended and never bypasses the gate. Host-tested model + ordering: `openpatch-core/tests/interlock.rs`. **UNVERIFIED on hardware**, and valid only once the board really implements the new gate: on the OLD board (`VMOT on = latch AND MCU_EN AND DOCKED`) a draw still fails the VMOT check (NoSupply). Pin: MOT_DIR stays where `docs/boards.md` / `board/e73.rs` put it until `electronics/bench/pin-assignment.md` is synced (one-file change: `board/e73.rs`). OPEN datasheet question: STSPIN220 latches MODE4/DIR at the STBY edge; in a draw DIR is at the reverse level then (DS11633 could not be fetched in this session): confirm full step does not depend on MODE4. Historical text of the old limitation follows.

   *Old limitation:* (limitation for `board-bench-e73`; solved in firmware for the DK and the syringe rig). `VMOT on = latch AND MCU_EN AND DOCKED` (hardware), but `AssistedFill` requires the pump UNDOCKED. On the bench board the
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
9. Bootloader ACL write protection (`openpatch_boot_policy::acl`, `docs/bootloader-v2.md`): TODO(verify-on-hardware) PERM read-back, BusFault on a write / erase of a bootloader page from the application, whether `ERASEUICR` / `ERASEALL` bypass it (the UICR rollback counter is not covered by the ACL).
10. Supervisor flashing over the STM32 ROM bootloader (`openpatch-supflash`, `docs/board-cup-v4.md`): host tested against a simulated bootloader only. TODO(verify-on-hardware): product id 0x443 (AN2606 not readable here), RDP probe behaviour, Readout Unprotect keeps nBOOT_SEL / BOR, all timeouts in `openpatch_supflash::timing`, 8E1 on the nRF UARTE. The embedded driver is not wired (image storage, minimum version source and UART hand-over are undefined).

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

## Rev A sync (2026-11-19): what is done, what is NOT verified

Implemented against `electronics/bench/pin-assignment.md` + `INTERLOCK.md` (host tested, **nothing has run on the controller**): the pin map (all 29 GPIOs), `DIR_FORWARD_HIGH = false` (feature `dir-forward-high` for R97), `UICR.NFCPINS` = GPIO, I_SENSE = mV / 6.67, the WAKE-synchronous DONE (EGU3 interrupt + permit),
the hardware-PPI DONE during a DFU swap, STBY low whenever idle, rotating single-gate disarm, POST-S and POST-A (gate legs, dock / DIR legs, over-current leg), Q4-short quarantine, FFC / pod presence, the simulator's board model with fault scenarios.

Remaining gaps (each is a known hole, not silently covered):

* **Catalogue**: no dedicated codes for the over-current leg (`1-07-007` inst 7 is reused) and for a latch that stays tripped (`1-07-005` is reused). Request to the catalogue owner (`spec/diag-codes.csv`, schema bump): `1-07-008 GATE_OC_STUCK_PASS` (L), `1-07-009 OC_LATCH_STUCK_TRIPPED` (F). A stuck-pass Q6 / Q10 pair can not be separated on Rev A (no mid-chain readback): both report `1-07-003`; `1-07-004` is raised only when the DIR leg keeps conducting after the flip.
* **Dock hall stuck at "docked"** (DRV5032 output stuck low) is invisible to the POST: DOCK_N and DOCKED_H agree, and `DOCK_TEST` proves the gate legs only. Only the app-guided lift test (A10, `2-21-001`) or a TMAG field cross-check can see it; the existing simulator scenario `hall_stuck_docked` shows the consequence.
* **Q4 shorted** can not be cut by anything on the board (USB is the last off switch). The controller keeps STBY low and raises `1-06-001` (L, REPLACE); detection needs `VMOT_SENSE` to work (a dead sense channel hides it; `1-08-*` / `1-09-001` catch some of that).
* A free-running DONE toggle faster than the 20 ms window keeps the TPL5010 alive (hardware limit, INTERLOCK.md B); our permit gating only covers the firmware's own DONE path.
* `EN/FAULT` at idle is not checked (`1-03-002`): the firmware drives it low while idle, and releasing it only to read it would need a documented STSPIN220 standby level.
* The POST-A over-current proof needs the motor connected (>= 60 mA holding current); without it the proof is UNKNOWN. Winding open / short signatures (`3-31-*`) are core-side checks and not part of the POST.
* The watchdog service test (A08) is not implemented (`Unsupported`).
* Timing constants (`VMOT_SETTLE_MS`, POST wait times, `OC_TRIP_MS`, the 12 ms over-current blanking) are design values; EGU3 / PPI ch2 / GPIOTE ch7 are assumed free of the radio stack.
* TMAG5273 plane (Y-Z) and range (+-80 mT) and the sign of the angle against the direction are UNVERIFIED (T12 / T5). The A1 part has the +-80 mT range bit (X_Y_RANGE / Z_RANGE); the A2 variants are the +-133 / +-266 mT parts.
* The post-draw take-up is now the lost motion of the current mechanics (0.33 mm = 623 steps on the 16:20 drive, `limits::LOST_MOTION_*`): it is larger than one minute of the 1.7 U/min backstop allows together with a prime, so the first prime after a draw runs the part of the take-up that fits and answers `Hourly`; the phone repeats the prime
  (the iOS app must treat `Hourly` after a draw as "repeat"). It changes with the new drive (push rod, play-free link).

## Assisted (pressure) fill (spec 3c, user decision 2026-11-19)

`FillDraw` is now `AssistedFill` in the Rust core / proto / simulator (wire command id `0x0F` and the TLV layout are UNCHANGED, so the C reference, the Swift app and every vector stay compatible; the Swift names were not touched). The retraction rate is fixed at `limits::ASSISTED_FILL_PPS` = 200 pps
(0.79 U/s; the needle-gauge cap can only lower it); the volume is booked from the confirmed travel; the interlock still allows reverse only undocked (`DIR_REV` leg); a prime is required before docking (`prime_required`, `Resume` refused with 26); stall monitoring is the existing draw stall + angle checks.
Simulator: `Plant::fill_push_kpa` (syringe pressure on the septum), actions `fill_push` / `fill_needle`, scenarios `assisted_fill_user_pushes`, `assisted_fill_user_pushes_hard`, `assisted_fill_user_does_not_push` (`tests/assisted_fill.rs`). The plant's water accounting under syringe pressure is NOT calibrated: those tests assert behaviour, not gravimetric volumes.

* **OPEN finding F7**: when the user does not push, the plunger (pulled by the carriage) draws air through the open outlet needle and the pod books the travel as water. Current and angle do not separate it (134 vs 136 mA). With a push-only coupling the carriage would separate from the plunger, but the current / angle signature is the same (the rod is unloaded when the plunger follows), so detection there needs an extra signal
  (plunger position, pressure). Ignored test `findings.rs::a_fill_nobody_pushes_is_stopped_and_not_booked`.
* A user who pushes too hard assists the motor (no stall), the excess leaves as drops at the needle tip; the pod never books more than the requested travel.
* docs/04-protocol.md, docs/06-diagnostics.md and the iOS app still call the command `FillDraw` / "draw": the rename there is for the doc / Swift owners (no wire change).
* The bench controller is PARKED (spec 4c): `board-bench-e73` stays compiling and tested, it is not extended further; next firmware work is `board-v010`.
