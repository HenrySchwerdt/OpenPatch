# OpenPatch Firmware

> Experimentelles DIY-Gerät, **kein Medizinprodukt**. Nicht am Menschen verwenden.

| Pfad | Inhalt | Status |
|---|---|---|
| `core/` | portabler C11-Kern (Abgabe-Engine, Sicherheitsüberwacher, Reservoir, Event-Log, Protokoll, Pump-Controller) | gebaut + getestet auf dem Host |
| `tests/` | Host-Testsuite (eigenes Mini-Framework, keine Netzwerk-Abhängigkeit), Mock-HAL | 129 Tests grün |
| `zephyr/` | nRF-Connect-SDK-Skelett (nRF54L15): `main.c`, HAL, GATT-Stub, Overlay | **NICHT gebaut, NICHT getestet** (kein NCS installiert) |
| `docs/openpatch-protocol.md` | Protokollspezifikation (deutsch) | |
| `docs/dash-compat.md` | Plan DASH-Kompatibilitätsmodus (deutsch) | Plan, kein Code |

## Host-Tests

```sh
cmake -S firmware -B firmware/build && cmake --build firmware/build && firmware/build/op_tests
firmware/scripts/coverage.sh   # LLVM-Coverage (clang + llvm-cov aus Homebrew-LLVM)
firmware/scripts/sanitize.sh   # ASan + UBSan
```
