# `board-cup-v4`: cup pod v4, 45 fitted parts (HJ-840 SiP, DRV8835, STM32C011 supervisor)

> TEST PROJECT, never worn. Water only.

Pins: `openpatch-bench/src/board/cup_v4.rs` is the single place (table in its header); the source of truth is `electronics/v010/design/netlist_v4.py` / `netlist_v4_cup.json` (the HJ-840 table in `FIRMWARE-PINMAP.md` is stale). Only the bring-up binary `src/bin/cup_bringup.rs` uses it so far:

```sh
cd firmware-rs/openpatch-bench
cargo build --release --target thumbv7em-none-eabihf --no-default-features --features board-cup-v4 --bin cup_bringup
```

The pump application (`main.rs`) is still the E73 / DK application and is NOT ported.

## Host tested pieces (`openpatch-core`, the bring-up binary only binds them to pins)

* `phase_drive`: DRV8835 full steps on `APHASE/AENBL/BPHASE/BENBL`. `(A,B)` = 00, 10, 11, 01 forward, reverse order for reverse, exactly one PHASE toggle per step (the supervisor counts these edges), brake (`AENBL = BENBL = 0`) at idle, PHASE lines untouched when de-energising, enables raised after and lowered before the phase lines.
* `burst`: bursts with rest gaps for the cell's peak current. `CellParams` (default Ampul 301030: 60 mAh realistic, 700 mA pulse limit, 150 ms, 90 mA average, 250 ms minimum rest) and `MotorLoad` (1.74 W, 88 %) are configurable PLACEHOLDERS: the vendor page gives no discharge rate. Default plan: 29 steps per burst at 200 pps, rest about 0.7 s at 3.8 V.
* `battery`: `vddhdiv5_to_mv` (SAADC `VDDHDIV5`, 12 bit, 0.6 V reference, gain 1/6: `mV = raw x 18000 / 4096`), motor start limit 3.4 V, `regout0_action` (`UICR.REGOUT0` = 3.3 V, HV mode: the HJ-840 has no LDO).
* `led`: charging pulse (red, 1 Hz), full = green, low = red (single flash, double below 3.4 V), fault 4 Hz, button shows the battery colour. `charger_state(usb_detected, stat_low)`: MCP73832 STAT cannot tell "done" from "no cable", so the cable comes from `USBDETECTED` (`VBUS_P`).
* `occlusion`: angle shortfall only (`SafetySupervisor::set_occlusion_source(AngleOnly)`): warning `5-53-004` above 1 U (two consecutive passes, hysteresis, auto clear on a new baseline), fault `5-53-001` above 2 U (spec 7, unchanged). The current-rise detector (`5-53-002/003`) is off on this board (no shunt).

## Supervisor (`openpatch-supervisor`)

Platform independent logic of the STM32C011: PHASE-edge step counting, arm window (600 ms, 1 s reverse), 32-step forward budget (permit drops with the 32nd step, the 33rd latches), dead time, H15 and direction consistency, over-current lock-out (2 s), 3 faults in 10 minutes lock until a power cycle, leaky buckets, status frame. Mandatory POST vector: declared reverse (`MOT_FWD` = 0) with forward phase order drops `SUP_PERMIT` in the handler of the first edge. Flashing through the ST ROM bootloader (8E1 UART, AN3155 framing) is only possible through a `FlashSession`, which needs VMOT below 0.3 V for 50 ms, undocked, no delivery, a verified image, and re-checks the supply before every frame.

Platform shell requirements (not in the repository): Stop mode with LPTIM / LSI (no 1 kHz sleep tick), option byte nBOOT_SEL = 0 at provisioning, `SUP_NRST` driven open drain only by the nRF.

## Hardware facts followed (review 2026-11-20)

The gate is `docked XOR reverse` (docked + reverse is cut in hardware; the core refuses it before a pin moves, the supervisor is a second line). `MCU_EN` is a hardware leg: direction first, then `ARM_CLK`, then `MCU_EN`; `MCU_EN` low before the direction returns to forward. The TPL5010 interval is about 2.0 s (`TPL5010_INTERVAL_MS`). I2C at 100 kHz, TMAG to sleep after boot. No 32 kHz crystal (`LfclkSource::InternalRC`).

## Not done

Porting the pump application to this board (replace the STSPIN220 `BenchCtl` / `Stepper` by `phase_drive` and the burst plan, `VMOT_SENSE` only), `USBDETECTED`, TMAG sleep, the TPL5010 kick path, the UART challenge/response, the nRF side of the supervisor update, the STM32C0 platform shell, USB DFU glue.
