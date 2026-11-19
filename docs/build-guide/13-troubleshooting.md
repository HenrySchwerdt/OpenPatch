# 13. Troubleshooting: diagnostic code or symptom to part to fix

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

**How to use this chapter.** First **unplug USB** if anything is hot, smoking, humming or moving by itself. Then find your code (section 13.2) or your symptom (13.3), replace or fix **one thing at a time** and repeat the test that failed.

**FRU** = field-replaceable unit, the part to change (names from `docs/06-diagnostics.md` 2.4): CTRL controller board, PODB pod sensor board, FFC cable, MOTOR (with its lead), GEAR pair, SCREW (leadscrew, nut, carriage), RESV reservoir, SEAL plunger seal, CAP end cap (septum and duckbill), NEEDLE, MAGD dock magnet, MAGS spindle magnet, USB supply, CANN (cannula or, here, dummy head), FW firmware.

**Latched codes (L) have no service override.** They clear only when their verification test passes after the fix (`docs/06-diagnostics.md` 3.5). Never bridge a gate, force the dock, or edit a calibration to clear one.

> **Status of the codes.** The catalogue in `docs/06-diagnostics.md` (150 codes) is the design. At the time of this guide the firmware raises the **legacy fault bits** (13.1) and log lines; the structured `L-CC-FFF` records, POST and the self-test commands are work packages WP-0 to WP-8 still in progress. A row marked **(design)** is what to expect once the record exists; today you reach the same FRU from the symptom.

## 13.1 Legacy fault bits and log lines you see today

| Fault bit / line | Catalogue codes | Meaning | First check |
|---|---|---|---|
| `OCCLUSION` (bit 0) | `5-53-001`, `5-53-002`, `5-53-003` | blockage: shortfall above 2 U or three bursts above the current threshold | outlet tube clamped or kinked, dummy-head septum plug blocking the bore, needle blocked, air |
| `ENCODER_DEVIATION` (bit 1) | `6-60-006`, `6-60-007`, `4-41-002` | angle per turn not within 3 %, or window above 10 % | **wrong drive preset (10.4.1)**, magnet loose, gap wrong, gears slipping |
| `RESERVOIR_EMPTY` (bit 2) | `5-50-001`, `5-50-003` | model at zero or an end stop reached | refill or draw; model and plunger position disagree |
| `BATTERY_CRITICAL` (bit 3) | `A-A0-002` | on the bench: the USB supply (`VBUS`) sags below 3.3 V-class limits | USB cable or port, current limit too low |
| `LIMIT_EXCEEDED` (bit 4) | `7-70-001` to `7-70-003` | a safety limit vetoed a request | your test exceeds 15 U/h, 1.7 U/min or 10 U: reduce, **do not raise limits** |
| `INTERNAL` (bit 5) | many | an internal check failed (for example `# prepare failed`, angle sensor missing) | read the log line above it |
| `NO_CALIBRATION` (bit 6) | `7-7D-001`, `7-7D-002` | calibration missing or **flash holds another preset than the build** | `settings: ... calibration Mismatch`: erase the settings page, re-provision |
| `WEAR_EXPIRED` (bit 7) | `B-B1-001` (44 h warning), `B-B1-002` (52 h, delivery stops) | pod worn longer than 52 h | endurance test: see 11.7; the catalogue says `Activate` clears it (swap-pod emulation) |
| `# waiting for DOCKED` | | headless sequence waits | dock the pod or bring the dummy-head magnet; check the hall (10.5) |
| `# rejected: ...` | | the command was refused: not docked (`Docked` 27), not suspended, `PrimeRequired` 26, `Limit`, `Busy` | the reason is in the line |
| `TMAG5273 not found` | `2-20-001`, `3-30-001` | I2C sensor does not answer | FFC pinout, pod board variant, address 0x35 |
| `DFU: the previous update was REVERTED` | | the new image crashed and the bootloader went back | flash again, read the log |

## 13.2 By diagnostic code (design: raised when WP-3 and WP-4 are merged)

| Code | Name | Sev | FRU: action | What it usually is on this bench build | Fix | Verify with |
|---|---|---|---|---|---|---|
| `1-01-001` | FLASH_IMAGE_BAD | F | FW: UPDATE_FW | interrupted flash, bad image | reflash bootloader then app (10.4.4) | POST-S S01 |
| `1-01-002` | BROWNOUT_RESET | W | USB: CHECK_POWER | weak USB, cable, bench supply limit at 300 mA | better supply, shorter cable, raise the limit to 500 mA | repeat the run |
| `1-01-003` | UICR_RESET_PIN_WRONG | F | FW: REPROVISION | UICR `PSELRESET` not P0.18: the TPL5010 cannot reset the MCU | `probe-rs erase` once, reflash, first boot writes it | S03 |
| `1-01-004` | NVM_VERIFY_FAIL | F | CTRL: REPLACE | flash write failed | erase settings, reflash; if repeated replace the module | write test |
| `1-02-001` | RAIL_3V3_LOW | F | USB (CTRL): CHECK_POWER | LDO input low, short on the 3V3 net | supply first; then a short on the controller (10.1) | S04 |
| `1-02-002` | RAIL_3V3_HIGH | L | CTRL: REPLACE | LDO fault | replace the controller board | S04 to S06 |
| `1-03-001` | DRIVER_FAULT_IN_BURST | F | MOTOR (CTRL): ISOLATE | STSPIN220 over-current or thermal: motor shorted, wrong phase pairing, current limit too high, motor jammed | unplug the motor and run A03: fault persists means controller; else motor or its plug pairing | A03 |
| `1-03-002` | DRIVER_FAULT_AT_IDLE | F | CTRL: REPLACE | `EN/FAULT` stuck low | replace the controller | S05 |
| `1-04-001` | WDT_TIMING_FAULT | L | CTRL: REPLACE | TPL5010 interval out of 1.4 to 2.6 s or no WAKE | check the TPL5010 and its resistor; replace the controller | A08 |
| `1-04-002` | WDT_RESET_INEFFECTIVE | L | CTRL: REPLACE | RSTn path broken | replace the controller | A08 |
| `1-05-001` | LATCH_CANNOT_CLEAR | L | CTRL: REPLACE | latch output stuck high: **motor supply cannot be cut** | **replace the controller. Do not use it** | A01 + A02 twice |
| `1-05-002` | LATCH_CANNOT_SET | F | CTRL: REPLACE | latch will not arm (fail-safe direction) | replace the controller | |
| `1-05-003` | LATCH_SET_WITHOUT_ARM | L | CTRL: REPLACE | latch high after reset | replace the controller | |
| `1-06-001` | VMOT_STUCK_ON | L | CTRL: REPLACE | motor supply on with all gates commanded open (P-FET or gate stuck, **the red VMOT LED lit with nothing running**) | unplug USB, replace the controller | A01 + A02 twice |
| `1-06-002` | VMOT_NOT_PRESENT | F | CTRL: REPLACE | armed and no supply: a gate blocks (dock gate with the pod undocked; draw without the DIR_REVERSE gate) | dock the pod; if docked, `1-07-006`/`1-07-005`; **do not bridge** | A02 |
| `1-06-003` | VMOT_DROOP | W | USB (CTRL) | supply sags under motor load | stronger supply, shorter cable | repeat |
| `1-07-001` to `1-07-004`, `1-07-007` | gate stuck pass / readback mismatch | L | CTRL: REPLACE | a protection gate no longer cuts | replace the controller | A01, A02 |
| `1-07-005` | GATE_MCUEN_STUCK_BLOCK | F | CTRL: REPLACE | MCU enable gate never opens | replace | |
| `1-07-006` | GATE_DOCK_STUCK_BLOCK | F | CTRL (PODB): ISOLATE | hall reads docked but the gate stays closed | check the FFC (pin DOCK_N), the pod hall; then controller | A02 |
| `1-08-001` to `1-08-003` | ISENSE_* | F/W | CTRL: REPLACE | current sensor offset, saturated or dead | replace | B22 |
| `1-0B-001` | LFXO_NOT_RUNNING | W | CTRL: REPLACE | 32.768 kHz crystal not running | replace the controller | S07 |
| `2-20-001` | TMAG_NO_ACK | F | PODB (FFC): ISOLATE | no I2C answer: **FFC pinout without I2C pins, FFC reversed, half inserted, wrong pod board** | check pin 1, re-seat, continuity SDA/SCL; if RB12 shows the loop open it is the FFC | S08 |
| `2-20-002` | TMAG_ID_MISMATCH | F | PODB: REPLACE | other sensor variant (A1 vs A2 address), register map unverified | check the part marking; verify on your sample | S08 |
| `2-20-003` | TMAG_FROZEN | F | PODB: REPLACE | identical angle with steps executed | replace the pod board; check the magnet is on the rod | A04 |
| `2-20-004` | TMAG_CRC_ERRORS | W | PODB (FFC): ISOLATE | noise | FFC away from the motor lead, re-seat | repeat |
| `2-20-005` | TMAG_DEVICE_STATUS | F | PODB: REPLACE | internal sensor error | replace | |
| `2-21-001` | DOCK_STUCK_DOCKED | L | PODB (MAGD): REPLACE | hall always docked: a stray magnet (the spindle magnet near the dock hall?) or a damaged hall | remove magnets, check the distance, replace the pod board; clears by A10 | A10 |
| `2-21-002` | DOCK_STUCK_UNDOCKED | W | MAGD (PODB): REDOCK | magnet not fitted or wrong face, insert not latched | flip the dock magnet (02.8), re-dock | 10.5 |
| `2-21-003` | DOCK_CHATTER | W | MAGD (PODB): REDOCK | the DRV5032FA switches about 4 mm early: a latch gap near the threshold | use the AJ variant; or a stronger magnet, or a closer seat | 10.5 |
| `3-30-001` | FFC_ABSENT | F | FFC: RECABLE | cable out, wrong connector | re-seat, check pin 1 | S08 |
| `3-30-002`, `3-30-003` | FFC_INTERMITTENT, I2C_BUS_STUCK | W/F | FFC (PODB): RESEAT | flip-lock not closed, cable folded | re-seat, replace the cable | B03 |
| `3-30-004` | FFC_DOCK_LINE_FAULT | F | FFC (PODB): REPLACE | dock line shorted to ground | replace the cable | |
| `3-31-001` | MOTOR_LEAD_OPEN | F | MOTOR: RESEAT | plug not seated; one wire broken | re-seat J5; **measure the coil resistance (26.5 ohm +-10 %)**; replace | A03 |
| `3-31-002` | MOTOR_PHASE_OPEN | F | MOTOR: REPLACE | one coil open | replace the motor | A03 |
| `3-31-003` | MOTOR_PHASE_SHORT | F | MOTOR (CTRL): ISOLATE | winding short or wrong wiring | unplug the motor, repeat A03 | |
| `3-31-004` | MOTOR_CONTACT_INTERMITTENT | W | MOTOR: RESEAT | plug or pin | re-seat, strain relief | |
| `4-40-001` | MOTOR_STALL_FREE | F | MOTOR (GEAR): REPLACE | stall with no pressure possible: **friction too high, gear binding, carriage jam** | 03.5 friction, 6.3 mesh, 6.2 travel | 11.1 |
| `4-40-002` | MOTOR_CURRENT_BASELINE_DRIFT | W | MOTOR | load changing (dry seal, dirt) | oil, clean | |
| `4-40-003` | DIR_INVERTED | L | MOTOR (CTRL): ISOLATE | reverse increases the angle: **motor phases swapped or the `DIR_REV` option wrong; an undocked pod could run forward** | check J5 wire order; do not run undocked | A04 |
| `4-41-001` | GEAR_BACKLASH_EXCESS | W | GEAR: REPLACE | gear play grows | check centre distance, wear | |
| `4-41-002` | GEAR_RATIO_MISMATCH | L | GEAR (CTRL): REPLACE | counts per pulse differ: class 2 (factor 0.8 or 1.25) = **wrong gear pair or a preset for another pair (gap G1)**; class 1 power of two = MODE pins | fit the right pair or build the right preset (10.4.1) | A05 |
| `4-41-003` | GEAR_TOOTH_SKIP | F | GEAR: REPLACE | gear A loose on the D-shaft, or gear B on the sleeve | re-fix with retaining compound (6.3) | A04, A05 |
| `4-42-001` | CARRIAGE_JAM_FWD | F | SCREW (GEAR): REPLACE | forward stall without pressure ramp: nut off-axis, rod bent, burr | 02.5, 04.1, 6.2 | 11.1 |
| `4-42-002` | CARRIAGE_FRICTION_HIGH | W | SCREW: REPLACE | friction rising | clean, oil the rod | |
| `4-42-003` | TRAVEL_LENGTH_MISMATCH | F | SCREW (MAGS): REPLACE | counts between stops do not match stroke x counts per mm | wrong rod length or pitch | first full draw |
| `5-50-001`, `5-50-002` | RESERVOIR_EMPTY, LOW | F/W | NONE: REFILL | model empty or low | refill (11.0, 11.4) | |
| `5-50-003` | RESERVOIR_MODEL_MISMATCH | F | RESV (MAGS): REFILL | end stop reached while the model says otherwise: **manual fill amount not matching the carriage position (11.0)** | re-fill and re-book | |
| `5-50-004` | DRAW_NO_SOURCE | F | CAP: RETRY | vacuum, needle not in the water or not through the septum | re-position the fill needle | 11.4 |
| `5-50-005` | AIR_OR_LEAK_SUSPECTED | W | CAP (SEAL): PRIME | air or a leak at the septum, cap spigot or seal | prime, re-seat the cap, check the plug | 11.5 |
| `5-51-001` | PLUNGER_FRICTION_PROFILE | W | SEAL: REPLACE | stick-slip | oil, recut the ring (03.2) | 03.5 |
| `5-53-001`, `5-53-002`, `5-53-003` | OCCLUSION_* | F/W | CANN (NEEDLE): CHECK_CANNULA | blocked tube, clamp, plug, needle | open the clamp; check the tube, the plug, the needle with a syringe | 11.3 |
| `6-60-001` | ANGLE_CHANNEL_LOST | F | PODB (FFC): ISOLATE | the sensor lost: follow the cause record (`2-20-*`, `3-30-*`) | | |
| `6-60-002` | FIELD_TOO_WEAK | F | MAGS (PODB): REPLACE | magnet off, wrong size, **gap too large** | re-glue the magnet, check 0.6 mm | S09 |
| `6-60-003` | FIELD_TOO_STRONG | F | MAGS: RETRY | another magnet nearby (the dock magnet near the sensor) | move magnets away | |
| `6-60-004` | ANGLE_NOISE_HIGH | W | PODB (FFC): ISOLATE | noise | cable routing | |
| `6-60-005` | ANGLE_JUMP | F | PODB (FFC): REPLACE | more than 2048 counts in 20 ms | sensor or loose magnet | |
| `6-60-006`, `6-60-007` | ENC_REV_DEVIATION, ENC_WINDOW_DEVIATION | F | GEAR (MOTOR): ISOLATE | angle does not match steps: preset, lost steps (motor too weak), loose gear | 10.4.1, 11.1 | |
| `6-60-008` | UNCOMMANDED_MOTION | L | CTRL (SCREW): ISOLATE | the plunger moved with the driver off: **back-driving by the seal pushing the screw (an unlocked, free screw)** or an interlock leak | check gear fit and thrust faces (6.3 step 7); clears with A09 | A09 |
| `6-62-001` | CURRENT_OVER_LIMIT | F | CTRL (MOTOR): ISOLATE | current above 1.5x the chopper limit | check VREF resistor, motor | |
| `7-74-001` | BOOT | I | | normal | | |
| `7-74-002`, `7-74-003` | UNEXPECTED_RESET, RESET_LOOP | W/L | | watchdog reset: a hang or brown-out | see the breadcrumb, power | |
| `7-74-005` | POST_INCOMPLETE | F | NONE: RETRY | a self-test step timed out | rerun | |
| `7-74-006` | POST_RESULT | I | | self-test summary: `ctx_b` must be 0 | | |
| `7-76-001` | INTERLOCK_FAILED_LATCH | L | CTRL: REPLACE | supply not verified cut; cause chain `1-05-*`, `1-06-*`, `1-07-*` | replace the controller | A01 |
| `7-77-001` to `7-77-003` | step count short / extra / PWM not stopped | F/L | CTRL (MOTOR) / FW | the hardware counter disagrees with the request | stop; report as a bug | |
| `7-7D-001`, `7-7D-002` | CAL_RECORD_INVALID, CAL_PRESET_MISMATCH | F | FW: REPROVISION | calibration missing, or the flash holds another preset than this build | erase the settings page and re-provision **with the right build** | S02 |
| `7-7D-003` | TEST_CAL_IN_BUILD | L | FW: UPDATE_FW | a host-test calibration is in the build | rebuild without `test-calibrations` | |

## 13.3 By symptom

### Mechanical and fluid

| Symptom | Likely cause | FRU | Fix | Where to check |
|---|---|---|---|---|
| Plunger does not move, motor stalls or hums | seal friction above the thrust; lid on the reservoir; gear binding; carriage jam | SEAL, SCREW, GEAR | measure 03.5; dye test 8.1; mesh 6.3; travel 6.2; reduce to one ring | 03.5, 11.1 |
| Motor vibrates but does not turn | phases paired wrong; one coil open; step rate too high | MOTOR / plug | measure coils (26.5 ohm); check J5 order; lower the rate | 10.2 |
| Motor runs, screw does not turn | gear A loose on the shaft (flat gap) | GEAR | retaining compound on the round bore | 6.3 step 6 |
| Gear grinding, rough turn | centre distance too small, gear not coplanar, gear tooth burr | GEAR | check coplanarity, deburr, seat the motor | 6.3 |
| Carriage rattles or bounces | nut float (AF 3.8 pocket), rod end float | SCREW | bond the nut; end float <= 0.1 mm | 04.1, 6.4 |
| Carriage jams at the rear | rear stop too early, rod too long | SCREW | file the carriage rear face; check rod length | 6.2 |
| Plunger does not follow the carriage in reverse | shim loose or bent | SCREW | re-seat the shim | 04.2 |
| Water leaks at the cap | spigot loose, septum plug loose | CAP | re-press, re-punch the plug; UV adhesive outside the joint (water only) | 05.4 |
| Water at the septum when the needle is out | plug torn or too small | CAP | new plug | 05.1 |
| Water on the dry side of the plunger | seal leaks or tore | SEAL | check the ring fit and squeeze; larger cast or ring | 03.2 |
| Air bubbles in the reservoir | fill too fast, dead layer 1.0 mm (no nose) | CAP, SEAL | fill tilted with the outlet up, fit the nose, prime | 11.0, 03.3 |
| Prime does not bring water to the tube | priming path 2.2 U, valve blocked, needle blocked | CAP, NEEDLE | repeat the prime several times, check the duckbill, blow through the needle with a syringe | 10.8 |
| No flow with the outlet open | needle blocked, duckbill stuck, plug blocking the bore | NEEDLE, CAP | clear each part | 05.3, 09.1 |
| Water flows with the motor off | duckbill leaks forward, pod above the outlet | CAP | test the valve (02.9), see the anti-siphon test | 11.5 |
| Pod will not dock / too stiff | arm hook too tight, dome larger than A | insert | next variant (9.2) | 09 |
| Pod falls off | hook overlap too small, pull-off 0.6 N | insert | taller hook variant (N 3.3) | 09 |
| Needle misses the septum | misaligned insert or bent needle | NEEDLE, insert | new needle, check the guide | 09.3 |
| Lid will not close, height above 8.5 mm | a part too tall, FFC pinched, gasket folded | | check 8.1, 8.3 | 08 |
| Screws spin in the boss | stripped PA12 | housing | thicker pilot fill with a drop of CA, or a new part | 08.3 |

### Electrical and firmware

| Symptom | Likely cause | FRU | Fix | Where to check |
|---|---|---|---|---|
| Nothing lights after USB | short, USB polarity, supply limit | USB, CTRL | check the 3V3 point, the supply limit, shorts | 10.2 |
| VMOT LED lit at power-up | **stuck-on gate** | CTRL | unplug at once; replace the board | `1-06-001` |
| `probe-rs` does not see the target | SWD wiring, VTref, board unpowered | probe | check the 10-pin ribbon, VTref, one supply only | 10.4.3 |
| Flash works, no log | RTT not attached, wrong chip | | `probe-rs run --chip nRF52840_xxAA`, check `.cargo/config.toml` | 10.4.4 |
| `settings: ... Mismatch` | flash holds another drive preset | FW | erase the settings page, reflash | 10.4.4 |
| `TMAG5273 not found` | FFC pinout, reversed cable, board variant | FFC, PODB | continuity SDA/SCL, pin 1, connector height | 07.4, 10.5 |
| `DOCKED` never asserts | magnet face wrong, too far, hall FA threshold | MAGD, PODB | flip the magnet, closer insert seat, AJ variant | 10.5 |
| `DOCKED` asserts at 8 mm | threshold too sensitive | PODB | AJ or ZE variant | 10.5 |
| `ENCODER_DEVIATION` at the first dose | **wrong preset** | FW | 10.4.1 | 10.4 |
| `ENCODER_DEVIATION` after minutes | magnet loose, gap, lost steps | MAGS | re-glue, re-gap | 6.4, 7.2 |
| `OCCLUSION` with the outlet open | threshold too low (140 mA) for your friction, or blockage | | compare the free-run current with the threshold (11.1); check the tube | 11.1 |
| No `OCCLUSION` with a clamp | threshold above the stalled current | | compare peak currents (11.3 step 5), report | 11.3 |
| Draw refused (`Docked` 27) | pod docked | | undock | 11.4 |
| Draw does nothing | controller without the DIR_REVERSE gate | CTRL | not possible on this revision | 10.0 C3 |
| BLE pairing fails | window closed (60 s), already bonded elsewhere | | press the button, remove the old bond | 10.7 |
| `# rejected: PrimeRequired` | no prime after a fill | | prime | 10.8 |
| `B-B0-001/002` temperature warnings (die proxy above 37 / 42 degC) | warm room, motor heat after long runs | none | let it cool, the pod suspends at 42 degC | `WAIT_COOL` |
| Pod resets every 2 s | TPL5010 not serviced: DONE line, or a hang | CTRL | check `1-04-*`, run the debugger | |

## 13.4 When the answer is not here

Write down the symptom, the log, the code and what you tried; attach photos; do not "fix" a safety limit or a gate. Open an issue with the report template (12.4).

Next: [14-disassembly-and-cleaning.md](14-disassembly-and-cleaning.md).
