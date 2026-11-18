# Projektstatus & Übergabe

> Diese Datei ist der **Einstiegspunkt für jede neue Session** (anderer Rechner, anderes Claude-Abo, andere Person).
> Sie wird bei jedem Push aktualisiert. Zuletzt aktualisiert: **2026-11-18**.

## Ziel

Eine Open-Source-Patch-Insulinpumpe („OpenPatch“). Sie ist abnehmbar, steckt auf eine Accu-Chek-Insight-Flex-Kanüle und hält mit Klett. Weitere Eckpunkte:
- Befüllung per Spritze, induktives Laden.
- Größen: 70, 100 und 200 IE.
- Bauhöhe ≤ 8,5 mm.
- Steuerung aus Trio, entweder über ein eigenes Kit oder über DASH-Emulation.
- Bestellbar bei PCBWay, Zielbudget ≤ 500 €.
- Montage **ohne Lötkolben**.
- Ziel: kleiner als alles, was es auf dem Markt gibt.

Alle Maße und Bauteile stehen in [spec/design-parameters.md](../spec/design-parameters.md). Das ist die **Single Source of Truth**.

## Stand pro Teilprojekt

| Bereich | Stand | Verifiziert | Offen |
|---|---|---|---|
| Mechanik ([mechanical/](../mechanical/)) | Parametrisches SolidCraft-Modell für 3 Größen, STEP/STL | `check.py`: alle 3 Größen PASS (38/42/55,4 × 32 × 8,5 mm) | Rev A mit echten Teilen in Arbeit: Motor/Spindel-Kaufteile, Lager, Dichtungen, Federkontakte, Kolbendichtung + Gießform, PCBWay-Druckordner, `ASSEMBLY.md`. Kanülentasche ist nur ein Platzhalter, bis die Insight Flex vermessen ist (`mechanical/cannula-measurement.md`). |
| Elektronik ([electronics/](../electronics/)) | SKiDL-Netzliste, BOM (51 Positionen), Pinbelegung, Platinenkontur als DXF | ERC sauber, 42 eigene Regelprüfungen bestehen | **KiCad-Layout + Autorouting + DRC + PCBWay-Paket in Arbeit.** Die ISP1807-Pad-Geometrie muss gegen das Datenblatt geprüft werden, sonst NICHT bestellen. Kosten geschätzt ~610 €, also über dem Budget. |
| Firmware ([firmware/](../firmware/)) | Portabler C-Kern: Delivery, Safety, Reservoir, Log, Protokoll | 129/129 Host-Tests, ~99 % Zeilenabdeckung | Zephyr-Build für ISP1807 (nRF52840) und nRF52840-DK in Arbeit. Offen: Krypto (AES-CCM nur Interface), DASH-Modus, `GetStatus` soll die letzte akzeptierte Sequenznummer zurückgeben. |
| iOS/Trio ([ios/](../ios/)) | `OpenPatchKit` (LoopKit-PumpManager) + `OpenPatchCore` | 88 Core-Tests + 36 Kit-Tests grün | Keine Verschlüsselung; nicht gegen echte Hardware getestet; HUD-Kachel fehlt. Integration: `ios/INTEGRATION.md`. |
| Website ([site/](../site/)) | Vite + three.js, 3D-Modell, Größen, Bauanleitung, BOM, Kosten | Build ok, three.js-Chunk 158 kB gzip | Workflow `.github/workflows/pages.yml`. Pages muss im Repo auf „GitHub Actions“ stehen. |

## Wichtige Entscheidungen (mit Begründung)

1. **Kein eigener ASIC.** Stattdessen das Funkmodul **ISP1807** (nRF52840, 8 × 8 × 1 mm, Antenne integriert) für Rev A. Ein ASIC kostet weit über 100 k€, und das Antennen-Layout auf der Mini-Platine wäre das größte Risiko. Für Rev B ist der nRF54L15 als nackter Chip geplant.
2. **Stadion-Reservoir 16 × 5 mm** statt Zylinder, damit die Bauhöhe von 8,5 mm möglich wird.
3. **Spindel neben dem Reservoir** mit Schlitten-Arm. Inline wäre die Pumpe etwa doppelt so lang.
4. **Qi-Spule Ø 17,6 mm.** Mit Ø 20 wäre sie 2,4 mm länger.
5. **Antrieb:** In Rev A ein Schrittmotor (0,0131 IE pro Schritt, mit Encoder geprüft). In Rev B ist ein **SMA-Ratschenantrieb** geplant (Omnipod-Prinzip, Patent US6656159 abgelaufen). Damit wird die Pumpe etwa 6–7 mm schmaler und wäre der kleinste 200-IE-Patch am Markt. Wiederbefüllbarkeit über eine ausrastbare Klinke; der SMA-Draht ist ein Verschleißteil.
6. **Keine Druck-und-Ventil-Dosierung**, weil sie bei einem Ventilfehler frei ausläuft. Auch **keine Piezo-Pumpe**, weil sie für Insulin nicht validiert ist.
7. **Omnipod 5 wird nicht emuliert.** Dafür bräuchte man signierte P-256-Transkripte und einen Key-Manager mit App Attest. Der DASH-Modus nach dem Vorbild von nightscout/ESP-Sim (GPL-3.0) reicht für Trio.
8. **CAD-Werkzeuge:** SolidCraft für 3D (CLI/MCP: `solidcraft-cli`), CADCraft für 2D (DXF/DWG; CADCraft kann kein 3D).
9. **Basal mit 48 Halbstunden-Segmenten**, kompatibel zu DASH.

## Nächste Schritte (Reihenfolge)

1. KiCad-Layout fertigstellen: ISP1807-Footprint verifizieren, Routing, DRC 0 Fehler, Gerber/CPL/BOM in `electronics/pcbway/`, `ORDER.md`.
2. Mechanik Rev A abschließen: Federkontakte, Anpressrippen, `out/pcbway/`, `ASSEMBLY.md`.
3. Firmware für `openpatch_reva` und `nrf52840dk/nrf52840` kompilieren und auf dem DK testen.
4. **Nutzer:** Kanüle mit dem Messschieber vermessen (Messblatt), danach die Kanülentasche anpassen.
5. Kosten auf ≤ 500 € bringen (3 statt 5 Platinen, günstigere Gehäuse oder Motoren) und dann bestellen.
6. Prüfstand: gravimetrische Fördergenauigkeit mit Wasser (siehe `docs/02-safety.md` §3).
7. Rev B: SMA-Ratschenantrieb, nRF54L15 als nackter Chip, Ziel 55 × 25 × 8,5 mm.

## So arbeitest du weiter (für eine neue Claude-Session)

- Lies zuerst `CLAUDE.md`, dann diese Datei, dann `spec/design-parameters.md`.
- Tests ausführen:
  - Firmware: `cmake -S firmware -B /tmp/fw && cmake --build /tmp/fw && ctest --test-dir /tmp/fw`
  - iOS: `cd ios/OpenPatchKit/OpenPatchCore && swift test`
  - Mechanik: `cd mechanical && python3 generate.py && python3 check.py`
  - Website: `cd site && npm ci && npm run build`
- Nach jeder Arbeitseinheit diese Datei aktualisieren und pushen.
