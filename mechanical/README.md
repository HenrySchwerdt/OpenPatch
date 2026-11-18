# OpenPatch – Mechanik (parametrisches CAD)

Experimentelles DIY-Gerät, **kein Medizinprodukt**. Quelle aller Maße: `../spec/design-parameters.md`.

**Genutzter Weg:** SolidCraft-Kommandoskripte (JSON) per `solidcraft-cli`, erzeugt von Python
(`generate.py`). build123d wurde nicht benötigt.

## Dateien

| Datei | Zweck |
|---|---|
| `params.json` | **einzige** Parametermenge (Maße, Spec-Ziele, Kanülen-Platzhalter A..N) |
| `op_layout.py` | berechnet Positionen aus den Parametern (Variante ändert nur `stroke`) |
| `op_cmds.py`, `op_build.py` | erzeugen das SolidCraft-Skript (alle Bauteile als getrennte Körper) |
| `generate.py` | Treiber: Skript -> `.sc`, STEP, STL, PNG |
| `check.py` | Höhe/Länge/Breite + Kollisionsprüfung (Exit-Code 1 bei Fehler) |
| `cannula-measurement.md` | Messblatt Insight-Flex-Kanülenkopf |
| `out/` | Ergebnisse mit Spec-Spule Ø20 |
| `out_coil176/` | Alternative: Spule Ø17,6 – hält alle Längenziele ein |

## Neu erzeugen

```bash
cd mechanical
python3 generate.py                         # OP-70/100/200 -> out/
python3 generate.py --sizes OP-100          # nur eine Größe
python3 generate.py --coil-d 17.6 --outdir out_coil176
python3 generate.py --set reservoir.fill_fraction=0.5 --set battery.y=16   # beliebige Parameter überschreiben
python3 check.py                            # prüft out/ (FAIL bei Länge > Ziel)
python3 check.py --ignore-length            # Länge nur als WARN
python3 check.py --outdir out_coil176
```

Voraussetzung: SolidCraft installiert unter `/Applications/SolidCraft.app` (anderer Pfad: Umgebungsvariable
`SOLIDCRAFT_CLI`; `check.py` nutzt denselben Standardpfad). Python 3 ohne Zusatzpakete.

## In SolidCraft öffnen

`out/OP-70.sc` (bzw. 100/200) in SolidCraft öffnen. Das Feature-Verlauf-Panel enthält alle Schritte,
die Parametertabelle `p_*` zeigt die Generatorwerte. **Achtung:** Skizzen (Langloch/Rechteck) nutzen feste
Zahlen, weil SolidCraft für Langlöcher keine Ausdrücke annimmt. Die Parameter in der `.sc` sind daher
Dokumentation. **Maßänderungen bitte in `params.json` machen und neu erzeugen**; in SolidCraft sind
einzelne Features (z. B. Pocket-Boxen) direkt editierbar. Körper: `bottom`, `top`, `reservoir`, `plunger`,
`leadscrew`, `motor`, `gearhead`, `gear_stage_a/b`, `battery`, `pcb`, `pcb_keepout`, `qi_coil`, `septum`,
`buzzer`, `needle`.

Schnittbilder (`*_section_y7.png`, `*_section_y22.png`): Blick von +Y, die Auslassseite/Kanülentasche liegt links.

## Ergebnisse (Spec-Spule Ø20, `out/`)

| Größe | L x B x H (mm) | Ziel L | Bemerkung |
|---|---|---|---|
| OP-70 | 40,40 x 32,0 x 8,50 | 38 | +2,40 |
| OP-100 | 44,40 x 32,0 x 8,50 | 42 | +2,40 |
| OP-200 | 57,80 x 32,0 x 8,50 | 56 | +1,80 |

Mit Spule Ø17,6 (`out_coil176/`): 38,00 / 42,00 / 55,40 x 32,0 x 8,50 – alle drei erfüllen die Ziele.
Keine Teilekollisionen in beiden Sätzen (Keep-out/Buzzer ausgenommen, dort sitzt das Bauteil im Keep-out).

## Konflikte mit der Spec (bewusst nicht still geändert)

1. **Höhe:** Stadion 16 x 5 innen + 2 x 0,8 Wand = 6,6 mm, plus 2 x 0,9 Gehäusewand = **8,4 mm**. Der Rest bis 8,5 mm
   ist 0,1 mm (Reservoir liegt auf dem Boden, 0,1 mm Luft zum Deckel – nicht die geforderten 0,15..0,2).
   **Ziel 8,0 mm ist damit unmöglich.** Minimal nötig für 8,0: Reservoirwand 0,8 -> 0,6 und Gehäusewand 0,9 -> 0,75,
   oder Reservoir-Innenhöhe 5,0 -> 4,5 (dann Breite 17,9 für gleiche Fläche). Die Gewölbe-Oberseite ist ebenfalls nicht
   möglich (flache Oberseite = 8,5); stattdessen Kantenradius 1,0 mm oben.
2. **Leadscrew "im Reservoir, trockene Seite, Mutter im Kolben":** erfordert Reservoirinnenlänge
   ca. `Totraum + 2 x Hub + 3,4` (die Spindel muss bei vollem Reservoir in einem hohlen Kolben stecken). Das ergäbe grob
   L = 48 / 56 / 83 mm statt 38 / 42 / 56. **Gewählt:** Spindel M1,6 in einer **Spur neben dem Reservoir**
   (zwischen Reservoir und Motor), Kolbenarm läuft durch einen Schlitz in der trockenen Reservoirwand zur Mutter.
   Dadurch gilt L ~ Hub + Konstante wie in der Spec. Motor (Ø6, 15,7 mm mit Getriebekopf) liegt in der dritten Spur;
   1:1-Stirnradstufe (Ø5) verbindet Motorwelle und Spindel. Das 10:1 steckt im Getriebekopf.
3. **Qi-Spule Ø20:** die Spule braucht 20 x 20 mm freie Fläche über Akku/Tasche (Reservoir/Motor sind vollhoch).
   Das kostet +2,4 mm (OP-70/100) bzw. +1,8 mm (OP-200). **Minimale Änderung:** Spule Ø17,6 (oder +2,4 mm Länge).
4. **Akku 302030 (20 x 30) passt nicht** neben Kanülentasche und Reservoir. Platzhalter: 3,2 x 19,8 x 17,2 mm (ca. 1000 mm3,
   grob 60..80 mAh – echtes Zellenmaß beim Hersteller prüfen).
5. **PCB "L-förmig um das Reservoir":** die Spuren neben dem Reservoir sind vollhoch belegt (Spindel, Motor). Das PCB
   liegt als Rechteck mit L-Ausschnitt (Septum-Boss) im Bereich B hinter dem Reservoir (ca. 19 x 29 mm).
   Hall-Sensor/Magnet (Encoder) ist noch nicht modelliert.

## Offene Punkte

- Kanülengeometrie ist Platzhalter (siehe `cannula-measurement.md`); H, K, L sind noch nicht in der Geometrie verdrahtet.
- Taster/Membran, Hall-Encoder, Motorhalterung und Dichtlippen sind nicht modelliert.
- Keine Dichtheits-/Reibungsanalyse; Wandstärken 0,5 mm am Septum-Boss sind nur mit SLA/MJF-Test zu bewerten.
- Spindelgewinde und Kolbenmutter sind glatte Zylinder/Bohrungen (Gewinde nicht modelliert).

## Bestellung bei PCBWay (3D-Druck, Prototyp)

- **Gehäuse (`*_bottom.stl`, `*_top.stl`):** bevorzugt **MJF PA12** (graues Nylon): zäh, Schnapp/Presssitz ok, Wand 0,9 mm
  machbar, aber raue Oberfläche und leicht porös -> **nicht wasserdicht**, für Wasserdichtheit nachlackieren/versiegeln oder
  später Spritzguss. Alternative **SLA** (Resin "Tough/ABS-like", z. B. 8000 / Somos Taro): glatte Oberfläche, feine Details
  (Nadelkanal 0,5 mm, Nut 1 mm) besser, aber spröder. Empfehlung: erste Runde beides, jeweils OP-70.
- Toleranzhinweis angeben: Spiel 0,15..0,2 mm eingeplant; Bohrung Ø0,5 / Ø0,9 (Nadelkanal) ggf. nachbohren.
- **Reservoir und Kolben (aus dem STEP `reservoir`, `plunger`):** nur für **Wassertests** (Maßprüfung, Gleitprobe). Nicht
  insulinverträglich / nicht steril. Für Insulin später COC/PP bzw. gekaufte Rohteile.
- Elektronik, Motor, Akku, Spule, Septum, Nadel und Buzzer sind Platzhalter und werden nicht gedruckt.
- Dateien: `out/OP-xx_bottom.stl`, `out/OP-xx_top.stl` (Einheit mm); Baugruppe zur Ansicht: `out/OP-xx_assembly.step`.
