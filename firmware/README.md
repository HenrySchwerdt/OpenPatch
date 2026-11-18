# OpenPatch Firmware

> Experimental DIY device, **not a medical device**. Do not use on humans.

| Path | Content | Status |
|---|---|---|
| `core/` | portable C11 core (delivery engine, safety supervisor, reservoir, event log, protocol, pump controller) | built + tested on the host |
| `tests/` | host test suite (own mini framework, no network dependency), mock HAL | 130 tests green |
| `zephyr/` | nRF Connect SDK v3.4.2 application: HAL, BLE GATT service, persistence, MCUboot/SMP DFU, custom board `openpatch_reva` | **builds for both targets; NOT tested on hardware** |
| `scripts/build.sh` | one-command build of Rev A + dev-kit images (signed, with MCUboot) | works |
| `ci/firmware.yml` | GitHub Actions workflow **draft** (not active; copy to `.github/workflows/` to enable) | untested |
| `docs/openpatch-protocol.md` | protocol specification | |
| `docs/dash-compat.md` | plan for the DASH compatibility mode | plan, no code |

## Host tests

```sh
cmake -S firmware -B firmware/build && cmake --build firmware/build && (cd firmware/build && ctest)
firmware/scripts/coverage.sh   # LLVM coverage (clang + llvm-cov from Homebrew LLVM)
firmware/scripts/sanitize.sh   # ASan + UBSan
```

## Target hardware

| Target | Board name | Use |
|---|---|---|
| Rev A pod | `openpatch_reva/nrf52840` | Insight SiP **ISP1807** (nRF52840). All pins in `zephyr/boards/openpatch/openpatch_reva/*.dts`, copied from `electronics/pin-assignment.md` |
| Dev kit | `nrf52840dk/nrf52840` | bench use before Rev A boards exist: encoder and battery are simulated, LED1 = buzzer, Button 1 = pod button |

No C file contains a pin number: every pin is a property of the `/zephyr,user` devicetree node (board dts, or `zephyr/boards/nrf52840dk_nrf52840.overlay` for the DK). A feature whose property is missing (safety latch, QDEC, charger) is compiled out.

## Toolchain (macOS, no sudo)

`nrfutil sdk-manager` on macOS can only install into `/opt/nordic/ncs` (needs root), so the toolchain is set up manually:

| Component | Location | Size |
|---|---|---|
| nRF Connect SDK v3.4.2 (west workspace, shallow) | `~/ncs/v3.4.2` | approx. 3.0 GB |
| Python venv with west + Zephyr/NCS/MCUboot requirements | `~/ncs/venv` | approx. 0.55 GB |
| Zephyr SDK 1.0.1, minimal + `arm-zephyr-eabi` GCC 14.3 | `~/zephyr-sdk-1.0.1` | approx. 1.4 GB |
| nrfutil 9.0.0 + `device`, `mcu-manager` | `~/.nrfutil` | 45 MB |

Re-create (what was done):

```sh
uv venv --python 3.13 ~/ncs/venv && VIRTUAL_ENV=~/ncs/venv uv pip install west
~/ncs/venv/bin/west init -m https://github.com/nrfconnect/sdk-nrf --mr v3.4.2 ~/ncs/v3.4.2
cd ~/ncs/v3.4.2 && ~/ncs/venv/bin/west update --narrow -o=--depth=1
VIRTUAL_ENV=~/ncs/venv uv pip install -r zephyr/scripts/requirements.txt -r nrf/scripts/requirements.txt -r bootloader/mcuboot/scripts/requirements.txt
# Zephyr SDK 1.0.1: zephyr-sdk-1.0.1_macos-aarch64_minimal.tar.xz and
# toolchain_gnu_macos-aarch64_arm-zephyr-eabi.tar.xz from github.com/zephyrproject-rtos/sdk-ng/releases
# (verify with sha256.sum), extract the toolchain into ~/zephyr-sdk-1.0.1/gnu/
```

## Build

```sh
firmware/scripts/build.sh all          # Rev A + dev kit
firmware/scripts/build.sh reva         # production-like: plaintext frames rejected
firmware/scripts/build.sh reva --dev   # bench pod WITHOUT insulin: + dev.conf (plaintext)
firmware/scripts/build.sh dk           # dev kit (always with dev.conf)
```

Artifacts in `firmware/build-zephyr/<reva|dk>/`:

| File | Purpose |
|---|---|
| `openpatch-<t>-merged.hex` | MCUboot + signed app, flash this on a blank board |
| `zephyr/zephyr/zephyr.signed.bin` | signed app only, for DFU over BLE (SMP) |
| `dfu_application.zip` | same, packaged for the nRF Connect Device Manager app |

The MCUboot signing key is generated on first build into `firmware/keys/mcuboot-ecdsa-p256.pem` (git-ignored). **Back it up**; whoever holds it can sign firmware that your pods accept. The SDK's public demo key is never used.

### Build results (NCS v3.4.2, 2026-11-18)

| Target | App flash | App RAM | MCUboot flash | Slot size |
|---|---|---|---|---|
| `openpatch_reva/nrf52840` (no dev.conf) | 261,848 B (55.1 % of slot) | 53,836 B (20.5 %) | 30,088 B of 48 KB | 474,986 B |
| `nrf52840dk/nrf52840` (dev.conf) | 262,656 B (55.3 %) | 53,836 B (20.5 %) | 30,120 B of 48 KB | 474,986 B |

Flash layout (nRF52840 standard partitions): MCUboot 0x0-0xC000, slot0 0xC000 (472 KB), slot1 0x82000 (472 KB), storage 0xF8000 (32 KB, settings/NVS + BLE bonds).

## Flashing

All options program the **merged hex**. For a first flash of Rev A use a full chip erase (the UICR `nRESET` pin setting on P0.18 is written at the first boot).

```sh
# nrfutil (J-Link on the DK's debug-out, or the DK itself)
nrfutil device program --firmware firmware/build-zephyr/reva/openpatch-reva-merged.hex \
    --options chip_erase_mode=ERASE_ALL,verify=VERIFY_READ --traits jlink
nrfutil device reset

# any J-Link
nrfjprog -f nrf52 --program firmware/build-zephyr/reva/openpatch-reva-merged.hex --chiperase --verify -r

# any CMSIS-DAP probe via pyOCD (pip install pyocd)
pyocd flash -t nrf52840 --erase chip firmware/build-zephyr/reva/openpatch-reva-merged.hex

# west (uses the runner configured in the board)
west flash -d firmware/build-zephyr/reva --runner jlink   # or --runner pyocd
```

**Rev A pod:** connect the probe to the TC2030-CTX-NL pads (SWDIO, SWDCLK, nRESET, 3V3, GND). Power the pod from its battery or the probe's target-supply pin; the TPL5010 resets the MCU if it is not served in time (see "Open issues": bootloader and watchdog).

**Dev kit:** `nrf52840dk/nrf52840` flashes through the on-board J-Link with `west flash` or `nrfutil device program`. Logs: RTT (`JLinkRTTViewer`, `nrfutil device ...`) and the DK's UART.

## Logging

The pod has no UART pads: logs go to SEGGER RTT over SWD (`CONFIG_LOG_BACKEND_RTT`).

## DFU over BLE (signed)

1. Suspend delivery from the phone (uploads are refused while the pod delivers).
2. Upload `zephyr.signed.bin` with the SMP service: nRF Connect Device Manager (iOS/Android, use `dfu_application.zip`), or `mcumgr --conntype ble --connstring peer_name='OpenPatch-XXXX' image upload zephyr.signed.bin`. The link must be bonded (button-press pairing first).
3. `image test` + reset. MCUboot verifies the ECDSA-P256 signature and swaps; the new image confirms itself after ten fault-free ticks (`boot_write_img_confirmed`), otherwise MCUboot reverts at the next reset.

## What is wired and what is stubbed

| Area | State |
|---|---|
| Core wiring (delivery engine, supervisor, reservoir, log, protocol) | wired through `op_hal_t` in `zephyr/src/hal_zephyr.c`, 1 s tick in `main.c` |
| Step generation | RTC2 counter alarm chain toggles STCK (no busy-wait), 100 steps/s |
| Safety latch (ARM_CLK / KILL_N / LATCH_Q_MON), VMOT rail check | implemented per `electronics/README.md` section 3 (unverified) |
| TPL5010 | WAKE interrupt answers DONE only if the main loop heartbeat is fresh; QDEC hall counts withhold DONE when the spindle does not move |
| Encoder | TMAG5273 angle over I2C (path A) + QDEC counts (path B); **register map from memory, VERIFY** |
| STSPIN220 mode pins | full-step via `CONFIG_OPENPATCH_STSPIN_MODE_BITS` (**VERIFY mode table**) |
| BLE | OpenPatch GATT service, LE Secure Connections only, pairing accepted only for 60 s after a button press, unbonded peers dropped, name `OpenPatch-XXXX` |
| Persistence | settings/NVS: event-ID ceiling, last accepted `seq`, reservoir (closes protocol open point 2/#3; see protocol section 6.1) |
| DFU | MCUboot (ECDSA-P256) + mcumgr SMP over BLE, upload gate while delivering, image self-confirmation |
| Button | short = pairing window / silence alarm; 3 s = emergency stop; charger detect suspends delivery |
| Charger (BQ25120A) | probe + INT/CHG pins only; charge current / SYS voltage are **not programmed** |
| Application-layer AES-CCM, session key agreement | **stub**: production config rejects every frame; `dev.conf` accepts plaintext |

## Open issues

1. **No application-layer crypto**: key agreement + PSA AES-CCM backend missing. A non-dev pod cannot be commanded.
2. **MCUboot vs. TPL5010**: the external watchdog (100 ms interval in the electronics design) resets the MCU during MCUboot's signature check unless the bootloader also answers WAKE with DONE (or the interval is longer at boot). Needs a bootloader hook or a hardware change.
3. Event log contents are RAM only (only the IDs persist).
4. QDEC runs continuously (power); hall/TMAG supply is always on (duty-cycling TODO). TMAG5273 is in standby between reads (about 3 ms per read).
5. Pairing is Just Works (no display): protected by the button window, not by MITM resistance.
6. Everything marked VERIFY (TMAG5273 registers, STSPIN220 mode bits, settle times, divider ratio) is unverified without hardware.
