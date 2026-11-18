| Modul-Pad | Pad-Nr. | Signal | Richtung | Funktion |
|---|---|---|---|---|
| P0.15 | 37 | `BTN_N` | in | Taster, Wake aus System-OFF (GPIO SENSE) |
| P0.17 | 27 | `QI_CHG_N` | in | BQ51003 CHG (open drain), Qi-Feld erkannt/Laden, Wake |
| P0.13 | 29 | `BQ_INT` | in | BQ25120A INT (open drain), Wake |
| P0.14 | 5 | `WDT_WAKE` | in | TPL5010 WAKE-Puls (GPIOTE-Interrupt) |
| P0.16 | 9 | `LATCH_Q_MON` | in | Rueck-Lesen des Sicherheits-Latch Q (MOT_ALLOW) |
| P0.26 | 6 | `I2C_SDA` | io | I2C (TWIM): BQ25120A (0x6A), TMAG5273 (0x35), 4.7k Pull-up nach 3V3 |
| P0.27 | 39 | `I2C_SCL` | io | I2C |
| P0.20 | 15 | `ARM_CLK` | out | Takt-Eingang Sicherheits-Latch (steigende Flanke = ARM) |
| P0.22 | 17 | `KILL_N` | out(od) | Open-Drain, Low = Latch loeschen (MCU-Pfad 'Motor aus') |
| P0.24 | 19 | `PER_EN` | out | BQ25120A LSCTRL -> VPER (Hall-Sensoren) schalten |
| P1.02 | 49 | `HALL_A` | in | DRV5032 #1 -> QDEC A (CPU-unabhaengig zaehlend) |
| P1.06 | 50 | `HALL_B` | in | DRV5032 #2 -> QDEC B |
| P0.04/AIN2 | 35 | `VMOT_SENSE` | ain | SAADC AIN2: Teiler 1.5M/1M auf VMOT (Rail-Check, Lastschalter-Test) |
| P0.05/AIN3 | 36 | `VBAT_SENSE` | ain | SAADC AIN3: Teiler 1.5M/1M auf VBAT (Redundanz zu BQ25120A-VBMON) |
| P0.08 | 32 | `TMAG_INT` | in | TMAG5273 INT (Data-Ready) |
| P0.06 | 34 | `WDT_DONE` | out | TPL5010 DONE (nur CPU-bedient, NICHT per PPI, solange Motor armed!) |
| P0.23 | 47 | `BUZ_PWM` | out | Piezo-Treiber (Gate Q1), PWM |
| P0.19 | 45 | `MOT_STCK` | out | STSPIN220 STCK/MODE3 (Step-Takt, PWM/GPIOTE) |
| P0.21 | 11 | `MOT_DIR` | out | STSPIN220 DIR/MODE4 |
| P1.15 | 51 | `MOT_MODE1` | out | STSPIN220 MODE1 |
| P1.14 | 52 | `MOT_MODE2` | out | STSPIN220 MODE2 |
| P1.13 | 53 | `MOT_STBY` | out | STSPIN220 STBY/RESET: High = Treiber aktiv (MCU-Enable, 100k Pulldown R72 -> fail-safe) |
| P1.05 | 54 | `MOT_EN_FAULT` | io(od) | STSPIN220 EN/FAULT: Fault lesen / optional per Low sperren (Treiber-intern Pull-up -> NICHT fail-safe) |
| P0.18/RESET | 13 | `NRST` | io | TPL5010 RSTn (Watchdog-Reset) + TC2030-Pad; P0.18 muss als RESET konfiguriert sein (UICR PSELRESET) |
| SWDIO | 28 | `SWDIO` | io | SWD (J1 TC2030 Pad 2) |
| SWDCLK | 30 | `SWDCLK` | in | SWD (J1 TC2030 Pad 4) |
| OUT_MOD / OUT_ANT | 22 / 20 | `RF_LINK` | rf | 0R R90 zwischen Modul-RF-Ausgang und Modul-Antenne (integrierte Antenne) |
| P0.09/NFC1 | 2 | `(frei)` | - | NC, NFC-Pad (nicht genutzt) |
| P0.10/NFC2 | 4 | `(frei)` | - | NC, NFC-Pad |
| (frei, NC) | - | - | - | 20 weitere GPIO-Pads bewusst unbeschaltet: P0.02/AIN0, P0.03/AIN1, P0.07/TRACECLK, P0.11/TRACEDATA2, P0.12/TRACEDATA1, P0.25, P0.28/AIN4, P0.29/AIN5, P0.30/AIN6, P0.31/AIN7, P1.00/TRACEDATA0, P1.01, P1.03, P1.04, P1.07, P1.08, P1.09/TRACEDATA3, P1.10, P1.11, P1.12 |
