# CLAUDE.md – Anweisungen für KI-Assistenten in diesem Repo

**Projekt:** OpenPatch, eine experimentelle Open-Source-Patch-Insulinpumpe. **Kein Medizinprodukt.** Sicherheit hat Vorrang vor allem anderen (siehe `docs/02-safety.md`).

## Einstieg
1. `docs/STATUS.md`: aktueller Stand, Entscheidungen, nächste Schritte
2. `spec/design-parameters.md`: Single Source of Truth für alle Maße, Bauteile und Grenzwerte. Änderungen zuerst dort, danach in den Teilprojekten nachziehen.

## Regeln
- Sprache der Doku: **Deutsch**. Code und Kommentare: Englisch ist ok.
- Sicherheitsgrenzen (Spec §7) dürfen nie stillschweigend gelockert werden.
- Der Hardware-Interlock (Motor nur mit MCU-Freigabe **und** Watchdog) bleibt in jeder Revision erhalten.
- Firmware-Kern und Swift-Kern werden testgetrieben entwickelt. Alle Tests müssen vor dem Commit grün sein.
- Mechanik: Nach jeder Änderung `mechanical/check.py` ausführen. Höhe ≤ 8,5 mm.
- Montage ohne Lötkolben (Spec §1a).
- Herstellerdatenblätter (PDF) nicht committen, sie sind über `.gitignore` ausgeschlossen.
- Nach jeder Arbeitseinheit `docs/STATUS.md` aktualisieren, committen (Conventional Commits) und pushen.

## Werkzeuge auf dem Entwickler-Mac
- SolidCraft (3D): `/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli`. MCP-Server: `solidcraft-cli mcp`
- CADCraft (2D, DXF/DWG): `/Applications/CADCraft.app`, Steuerserver: `--control <PORT>`
- KiCad 10: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`
- nRF Connect SDK: `nrfutil` (Homebrew), SDK unter `~/ncs`
