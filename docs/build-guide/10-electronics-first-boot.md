# 10. Electronics: controller board, power, flashing, first boot, self-test, pairing

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

> **To be confirmed when the controller board is final.** This chapter is written against the files in the repository **today** (`electronics/bench/pin-assignment.md`, `electronics/bench/controller/parts.json`, `electronics/bench/fab/jlcpcb/controller/`, `firmware-rs/docs/boards.md`, `firmware-rs/docs/bench-testing.md`, `docs/06-diagnostics.md`). The controller board is still being finished by another work package: the interlock gate, the FFC pinout and the pin map are not frozen. Every item marked **(confirm)** must be checked against the final `electronics/bench/pin-assignment.md` and `ORDER.md` before you connect anything. **If this chapter and the final board disagree, the board documentation wins.**

## 10.0 What is open (confirm list)

| # | Item | State in the repository today | What to do |
|---|---|---|---|
| C1 | **FFC pin count and pinout** | pod board 10 pin (FH12-10S, C506791), `pin-assignment.md` 12 pin (FH12-12S, SMA concept), `BOM-jlcpcb.csv` 16 pin (FH12-16S, C596731) | use the connector and cable named in the final `ORDER.md`. If controller and pod still differ in pin count, **stop**: do not adapt by hand |
| C2 | **Pin map** | `pin-assignment.md` documents the SMA concept (pad 1 `DOCK_N`, pad 12 `I2C_SDA`, ...), `firmware-rs/docs/boards.md` implements a **stepper** map (pad 1 `MOT_STBY`, pad 3 `DOCK_N`, pad 22 `MOT_DIR`, ...) | the firmware `board/e73.rs` pins must equal the final board; a one-file sync (`docs/stubs.md`) |
| C3 | **Interlock gate** | decided: `VMOT = MCU_EN AND latch AND (DOCKED OR DIR_REVERSE)`; older boards only `... AND DOCKED` | for the **draw test** (11.4) you need a board with the DIR_REVERSE gate. **Never jumper the docked gate to force a draw.** On an old revision the draw test is "not possible" and is reported as such |
| C4 | **Motor current limit** | `pin-assignment.md`: VREF 0.160 V, sense 1.0 ohm = 160 mA; `boards.md`: I_SENSE 20 V/V x 1.0 ohm, MOT_REF 105 mA; sim: 105 mA limit gives 4.0 N, rated 181 mA gives 7.0 N | read the value on your board (R24 or R69) and record it; thrust tests depend on it |
| C5 | **Motor connector** | J5 Molex PicoBlade-compatible (A1251WR-S-4P, C225113), J6 JST GH (DNP footprint) | look at the plug on your motor (02.3) |
| C6 | **Readbacks RB1 to RB5, RB12 (FFC loop)** | requested by `docs/06-diagnostics.md` section 3.1, not yet on the board | the self-test (10.6) cannot identify which gate is stuck without them |

## 10.1 Receive and inspect the controller board

The board comes as a JLCPCB assembled PCB (about 40 x 50 mm, 4 layers, 1.6 mm). Main parts: E73 module (U1), STSPIN220 stepper driver (U4), TPL5010 watchdog (U5), SN74AUP1G74 latch (U6), INA180 current sense (U7), USB-C power-only receptacle (J1), SWD header 2 x 5 1.27 mm (J3), FFC connector (J4), motor connector (J5), buzzer (BZ1), status and alarm LEDs, button (SW1). **No soldering iron is needed.**

1. Under the loupe: the E73 module (castellated pads) is flat and all 43 pads are wetted, the STSPIN220 QFN has no bridges, the connectors sit square.
2. Multimeter, **board unpowered**: 5 V rail (VBUS) to GND and 3V3 to GND must not be a short (above about 100 ohm after the capacitors settle).
3. **Check:** nothing missing, no shorts. **Fail:** do not power the board, return it.

## 10.2 Connections and power

1. **Motor:** plug the factory lead into J5 (or J6 if you have the JST GH plug and an assembled J6). **The wire order must match the silk screen.** The pin order in `pin-assignment.md` is B-, A-, B+, A+; the motor drawing gives B, A-, B+, A at the pins (**confirm** with the plug you actually hold). Before you connect: measure the coil resistance of the four wires with a multimeter: two pairs of about **26.5 ohm +-10 %** each, and open between the pairs. Connecting a coil pair to the wrong outputs makes the motor vibrate instead of rotate: unplug.
2. **FFC:** into J4 on the controller (**confirm C1**); pin 1 to pin 1 as printed on the silk. Do a **continuity test** from the controller connector to the pod board before you apply power.
3. **USB-C:** a 5 V source that can supply at least 500 mA (a bench supply with the limit set to 300 mA for the first power-up, or a good USB port). **Do not connect a battery or any other source.** The USB-C is power only: there is no USB data.
4. **First power-up with current limit 300 mA, the pod docked (magnet near) or not, SWD not connected yet:**

| Check | Pass | Fail |
|---|---|---|
| 3V3 test point | 3.3 V +-0.1 V | no regulator output: check USB polarity (a USB-C cable is symmetric, a bench supply lead is not), power off |
| Idle current at 5 V | record it; the module and driver idle are small, **above about 150 mA at idle**: unplug | a short or a hot part: find it with the thermal sense of your finger on the STSPIN220 and the LDO after 10 seconds; power off |
| Green status LED | lit or blinking after boot | nothing: flash first (10.4) |
| **VMOT LED (red)** | **off** (the motor supply is gated: `VMOT = MCU_EN AND latch AND docked`) | if it is **on** with the firmware not running: **latched stuck-on gate** (`1-06-001`); unplug immediately, do not attach the motor, see chapter 13 |

## 10.3 Toolchain (once)

Follow `docs/SETUP.md`. In short (Linux, macOS, Windows):

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add thumbv7em-none-eabihf
cargo install probe-rs-tools --locked        # then the probe-rs udev rules (see probe.rs docs)
cargo install flip-link cargo-binutils
# libclang is needed for the BLE stack bindgen (nrf-sdc)
```

Test the host side of the firmware first: `cd firmware-rs && cargo test --workspace` (several hundred tests; all must pass before you flash).

## 10.4 Flashing

### 10.4.1 The drive preset (gap G1, read this first)

The firmware has **no default drive**: exactly one cargo feature `drive-*` must be chosen, and it fixes how much water one motor step delivers and how many angle counts one step must produce. The pod in this guide uses the **16 : 20 step-down pair**. The repository's presets are `drive-nfp-608-26-45-g15-12` (6.1697 mU/step, 423.2 steps per screw turn), `g1-1` (4.9355 mU/step, 529 steps per turn), syringe rig, Zhaowei, Faulhaber: **none is the 16:20 pair**. With a wrong preset the angle check compares 6.19 counts per step (real) against 9.68 (g15-12), a deviation of about -36 %, far over the +-3 % per turn limit: the core **latches `ENCODER_DEVIATION` at the first dose**. A pod with the wrong preset cannot be used for the tests of chapter 11, and **must not be forced** by disabling the check.

| Quantity | Value for the 16 : 20 pod | Source |
|---|---|---|
| steps per motor turn | 20 | datasheet |
| planetary ratio | 26.45 | datasheet |
| gear pair, motor : screw | 16 : 20, the screw turns 0.8 per motor turn | `params.json bench.gears` |
| effective ratio | 26.45 x 20/16 = **33.0625** (x100 = 3306.25, **not an integer**: the preset structure `gear_ratio_x100` needs an extension or an agreed rounding to 3306) | derived |
| steps per screw turn | **661.25** | derived |
| angle counts per step (4096 per turn) | **6.194** | derived |
| water per step | **3 948.6 uU = 2 088 800 / 529 uU** with the core's 74.6 mm2 area (spec §4 quotes 0.003951 U with 74.63 mm2) | derived; same rational form as `drive_cal.rs` |
| 0.05 U in steps | 12.66 steps (the core accumulates the remainder exactly) | sim 2.1 |

**What to do:** wait for the firmware owner to publish the preset (a new `DriveId` and `drive-nfp-608-26-45-g16-20` feature), then build with it. If you are a developer and add it yourself, add the preset to `openpatch-core/src/drive_cal.rs`, add the feature to `openpatch-bench/Cargo.toml`, run `cargo test --workspace` (the differential tests will tell you what else assumed the ratio), and treat the result as a **bench-only fork** that you describe in your test report. **Do not edit a calibration to hide a mechanical finding** (`firmware-rs/docs/bench-testing.md`). The name used below, `drive-nfp-608-26-45-g16-20`, is a proposal, not an existing feature.

### 10.4.2 Signing key and bootloader (once)

```sh
cd firmware-rs
./scripts/gen-signing-key.sh        # once: keys land in firmware-rs/keys/ (git-ignored). Back them up offline. Never commit the private key.
scripts/build.sh --dev              # builds bootloader + apps; --dev enables dev-plaintext (bench only)
```

### 10.4.3 Connect the probe

Use the nRF52840-DK as a probe: its **Debug out** connector to the controller's SWD header J3 (2 x 5, 1.27 mm: 1 VTref, 2 SWDIO, 4 SWDCLK, 10 nRESET, 3, 5, 9 GND) with a 10-pin ribbon. Follow the DK documentation for using "Debug out" with an external target: the controller has its own USB 5 V supply, the DK must only provide the SWD signals and sense VTref, so make sure that **only one source** feeds the controller's 3V3. Use a Tag-Connect TC2030 on J2 if you prefer. **Never connect a probe that is powering the board while USB is also connected** (two supplies). Check that `probe-rs list` shows the probe.

### 10.4.4 Flash

```sh
cd firmware-rs/openpatch-bootloader && cargo run --release            # 1. bootloader first (probe-rs, SWD)
cd ../openpatch-bench && cargo run --release --features drive-nfp-608-26-45-g16-20,dev-plaintext   # 2. app, RTT log
```

`cargo run` uses `probe-rs run --chip nRF52840_xxAA` (`.cargo/config.toml`) and prints the defmt log over RTT. The application is linked at 0x9000 behind the bootloader: **always flash the bootloader first.** On a fresh E73 module the first boot writes `UICR.PSELRESET` = P0.18 and resets once; if the log says the UICR holds another value, erase it once (`probe-rs erase`).

**Check after flashing:** the log shows `settings: ... calibration FirstBoot` (first time) or `Match` (later). `Mismatch` means the flash holds another drive than the build: **no delivery, nothing is overwritten**; erase the settings page to re-provision. **Fail:** build or flash errors: see chapter 13.

## 10.5 First boot with the lid off (recommended)

If you closed the lid in chapter 08, remove its four screws for this section (you want to see the carriage). **Keep the pod undocked, outlet needle free, reservoir empty.** No water yet.

1. Power on (USB, current limit 300 mA). The log must show, in this order (wording may vary): firmware version, board feature `board-bench-e73`, the **calibration line** (above), interlock check, `TMAG5273` found at 0x35 with a field magnitude, `# waiting for DOCKED` (if the bench autostart feature is on). **Pass:** all present, no `# prepare failed`, no fault bits.
2. **TMAG probe:** if the log says `TMAG5273 not found`: the sensor does not answer: FFC, solder joint, address, or the pod board is the wrong variant (10-pin FFC with no I2C pins, see `docs/stubs.md` conflict 1). Without the sensor the default build (`angle-tmag`) **never delivers**. The `angle-qdec-fallback` build exists but is **not sufficient** (it cannot satisfy the 3 % per turn check): do not use it for the tests.
3. **Angle channel check (no motor power needed):** rotate the leadscrew by hand with the pin vise on the rod end: the angle value in the log or the `angle_counts` column changes smoothly by **4096 counts per turn**, in a consistent direction. A jump of more than 2048 counts between 20 ms samples would break the unwrap. **Pass:** smooth. **Fail:** noise or jumps: magnet gap (7.2), a metal object near the sensor, a loose magnet.
4. **Dock hall:** bring the dummy head's magnet toward the pod's dock window slowly and note the distance at which `DOCKED` asserts (and the log line, or LED, or the GetStatus flag). **The FA part asserts about 4 mm before full latch** (STATUS; PARTS-LOCK row 10 predicts 4.8 to 7.3 mm for FA/FB, 3.7 to 5.1 mm for AJ). Record both the assert distance and the release distance. **Pass:** asserts when latched and **not** at 8 mm; releases when you pull off. **Fail:** asserts only when the pod is not latched (too early): the latch gate is then not meaningful; use the AJ variant (PARTS-LOCK row 10). Never jumper the gate. If the magnet face does not trigger it, flip the magnet (02.8).
5. **Interlock proof with the scope (optional but recommended):** probe `MCU_EN`, `ARM_CLK` and `VMOT` (the test points on the board). With the firmware running, `VMOT` rises only during a command and falls after it. **Hold the firmware in the debugger** (or reset into a hang) and confirm that **VMOT drops within about 2 s** (the TPL5010 timeout; sim `hang_runaway`: the pod reset after 1.9 s and about 389 steps ran before the cut). Record the time.

## 10.6 Self-test (POST) and expected diagnostic codes

`docs/06-diagnostics.md` defines two self-tests. **They are a design (work packages WP-0/1/3/4/5 in progress). Only part of them runs in the firmware of this repository today: the legacy fault bits, the calibration match, the interlock verification and the TMAG probe.** There are no diagnostic records (`L-CC-FFF` codes) in the Rust source yet; the table says what a healthy bench pod will show **when WP-3 is merged** and what you see **today**.

**POST-S (passive, every boot, at most 1.5 s, the motor is never driven):** S01 image CRC / signature, S02 calibration record (present, CRC, range, equals the build preset), S03 `UICR.PSELRESET`, S04 3V3 rail and reset cause, S05 latch low and the control outputs read back as driven, S06 all gates open: `VMOT_SENSE` below 0.5 V and the current sensor offset small, S07 clocks, S08 FFC present and TMAG ACK at 0x35 with device ID, S09 magnet field 50 % to 160 % of nominal, S10 dock input plausible, S11 temperature, S12 button not stuck, S13 fault log readable, S14 latched codes from the last run.

**POST-A (active; pod suspended; at most 5 s; a net-zero excursion of 16 steps reverse then 16 steps forward, about 0.063 U on the 16:20 drive):** A01 each gate can cut the supply, one at a time; A02 dock and direction gates block when undocked; A03 current baseline; A04 direction polarity (reverse decreases the angle); A05 step ratio (counts per pulse within +-5 % of the calibration, and it classifies 0.8 or 1.25 as a wrong gear pair); A06 backlash; A07 compliance with the closed system; A08 watchdog (service command, resets the MCU); A09 uncommanded motion; A10 dock lift proof (app-guided); A11 alarm path (user confirms the beep).

**Expected on a healthy bench pod (after WP-3):**

| Record | Code | Severity | Meaning | When |
|---|---|---|---|---|
| BOOT | `7-74-001` | I | pod started, reset cause, firmware version | every boot |
| POST_RESULT | `7-74-006` | I | end of POST-S: `ctx_a` = mask of steps passed (bits S01 to S14 set where applicable), `ctx_b` = mask of steps failed (**0**) | end of POST-S and POST-A |
| (nothing else) | | | no W/F/L code | |

**Expected on the bench controller in particular:** A11 (alarm path) raises `1-0C-002 ALARM_UNCONFIRMED` (W) if you answer "no beep heard"; the proofs of the forward-dependent gates stay **UNKNOWN** (grey) while the pod is undocked, and the DK build reports every interlock proof as UNKNOWN, never OK. The `ENCODER` and ratio checks (A04, A05) need the angle sensor and the right drive preset: with a wrong preset A05 returns `4-41-002 GEAR_RATIO_MISMATCH` (L, latched, class 2: factor 0.8 or 1.25), exactly the failure of gap G1.

**What you see today (legacy):** the fault bits of `GetStatus`/the CSV `faults` column: `OCCLUSION` (bit 0), `ENCODER_DEVIATION` (1), `RESERVOIR_EMPTY` (2), `BATTERY_CRITICAL` (3), `LIMIT_EXCEEDED` (4), `INTERNAL` (5), `NO_CALIBRATION` (6), `WEAR_EXPIRED` (7); log lines `# prepare failed code=N`, `# rejected: ...`, `settings: ... calibration Mismatch`, `DFU: the previous update was REVERTED`, and the protocol results `Docked` (27), `PrimeRequired` (26), `Limit`, `Busy`, `Fault`. Chapter 13 maps both worlds to a part and a fix.

**Pass criterion for 10.6:** no fault bit and no `W/F/L` record at idle after boot; the boot log has the calibration line `Match`; the angle channel works; the dock asserts. **Fail:** chapter 13, by code.

## 10.7 Pairing with the bench app or a dev build

The pod has no screen. Three ways to talk to it, all **against a pod on the bench with water**, never against a person:

1. **BLE bench service from a generic BLE tool** (nRF Connect on a phone). Press the **button on the controller**: it opens the pairing window (60 s, bonding). Connect from the phone and **pair/bond within 60 s**; all bench characteristics need an encrypted link. The service UUID is `2E092A48-506C-477E-ADD4-448BF1490010`; **Control** (`...1490011`, write): `op u8` (1 start, 2 abort), then for start `pulses u16`, `amount_mu u32`, `pause_ms u32`, little endian (11 bytes); **Log** (`...1490012`, notify): one ASCII line per notification (CSV header, rows, `# ...` comments). Example: start 10 pulses of 1 U with 30 s pause: `01 0A00 E8030000 30750000`. A button hold of 3 s or the abort op stops a sequence.
2. **Headless (compile-time defaults):** `OPENPATCH_BENCH_PULSES=10 OPENPATCH_BENCH_AMOUNT_MU=1000 OPENPATCH_BENCH_PAUSE_MS=30000 OPENPATCH_BENCH_FILL_MU=50000 cargo run --release --features drive-...,dev-plaintext,bench-autostart`. The sequence starts at boot as soon as `DOCKED` is asserted (amounts in mU, multiples of 50, i.e. 0.05 U). Defaults: 10 x 1.000 U with a 30 s pause.
3. **OpenPatchKit development build** (`ios/INTEGRATION.md`, Xcode, iOS 17 or later; experimental, simulator-tested only): pairing with the application-layer handshake inside the same button window (`docs/04-protocol.md` section 5), then fill, prime and bolus commands. Use it only with the pod on the bench.

`dev-plaintext` (set by `--dev`) accepts plaintext frames and the public development key. A production build refuses every frame until the phone completed the key agreement. **Never use `dev-plaintext` with anything that is not a bench pod on a table.**

**Check:** the phone shows the Log characteristic lines; a start op with the pod docked and primed produces CSV rows. **Fail:** `# rejected: ...` lines name the reason (not docked, not suspended, prime required, limit).

## 10.8 Priming (required before the first dose)

A fill or draw sets `PRIME_REQUIRED`; `Resume` is refused with `PrimeRequired` (26) until a prime completed. The bench `prepare` primes automatically (0.2 U of water through the connector). The simulation says the **priming path holds 2.2 U** while the prime limit is 0.524 U (`MAX_PRIME`), so **several prime commands may be needed** and the water must be seen to reach the dummy head (sim 5.1). Prime with the dummy head docked and the tube end over the beaker. Record the number of primes and the total steps.

Next: [11-water-bench-tests.md](11-water-bench-tests.md).
