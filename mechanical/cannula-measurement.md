# Messblatt: Accu-Chek Insight Flex – Kanülenkopf (Konnektorplatte)

Ziel: Die Aufnahmetasche an der Unterseite des Pods passt nur, wenn wir die echte Geometrie des
Kanülenkopfs kennen. Roche veröffentlicht sie nicht. Bitte mit **Messschieber (0,01 mm)** messen.

**Wichtig:** Den Kanülenkopf **nicht** am Körper messen. Ein *neues, unbenutztes* Set verwenden
(Schlauch abgezogen, Konnektorplatte frei). Nadel/Kanüle nicht berühren (Stichgefahr, Sterilität).
Jede Größe 3x messen und den Mittelwert eintragen. Wenn ein Maß nicht messbar ist: leer lassen,
der Platzhalter bleibt dann aktiv.

## Skizze (Draufsicht von der Schlauchseite, X = lange Seite der Platte)

```
                 A  (Plattenlänge, X)
      |<------------------------------------->|
      |      K (Eckenradius)                  |
   ---+---------------------------------------+---   ^
   |  ,-------------------------------------,  |     |
   |  |                                     |  |     |
 D |->|        ( H  Septum-Ø )              |<-|     B  (Plattenbreite, Y)
   |  |            +  <- Septum-Mitte        |  |     |
   |  |          I,J = Versatz der Mitte     |  |     |
   |  '-------------------------------------'  |     |
   ---+---------------------------------------+---   v
      |<-E->|  Schnappflügel (links/rechts)
```

Seitenansicht (Blick entlang Y):

```
        ____________________           ---
       |  Konnektorplatte   |           ^
   ====|=== Flügel ====     |==== G     | C  (Plattendicke)
       |        (F hoch)    |           v
       |____________________|          ---
            |  Kanüle  |   <- L  (Abstand Plattenunterseite bis Kanülenaustritt / Sockel)
    M = Nadeleindringtiefe in das Septum (von der Plattenoberseite aus)
```

## Messwerte

| Buchstabe | Was messen | Schieber-Methode | Platzhalter (mm) | Eintrag in `params.json` (`cannula.`) | Ihr Wert |
|---|---|---|---|---|---|
| **A** | Plattenlänge (lange Kante) | Außenmaß | 14,0 | `A_plate_length` | |
| **B** | Plattenbreite (kurze Kante) | Außenmaß | 10,0 | `B_plate_width` | |
| **C** | Plattendicke ohne Flügel | Außenmaß, Seitenansicht | 3,0 | `C_plate_thickness` | |
| **D** | Tiefe der Schnapp-Nut / Höhe der Flügelnase (wie weit steht die Nase über die Plattenkante) | Tiefenmaß oder Differenz der Außenmaße mit/ohne Flügel | 1,0 | `D_wing_groove_depth` | |
| **E** | Länge der Flügelnase entlang der Kante | Innenmaß der Schieberschnäbel | 3,0 | `E_wing_len` | |
| **F** | Höhe (Dicke) der Flügelnase | Seitenansicht | 1,0 | `F_wing_height` | |
| **G** | Abstand Unterkante Platte bis Unterkante Flügelnase | Tiefenmaß | 1,0 | `G_wing_z` | |
| **H** | Durchmesser des Septums (sichtbare Silikonfläche) | Innenmaß | 4,0 | `H_septum_dia` *(noch nicht in Geometrie verdrahtet, nur Doku)* | |
| **I** | Versatz Septum-Mitte zur Plattenmitte in A-Richtung (+ = zur Flügelseite 1) | Abstand Kante-Septumrand, dann umrechnen | 0,0 | `I_septum_off_x` | |
| **J** | Versatz Septum-Mitte zur Plattenmitte in B-Richtung | wie I | 0,0 | `J_septum_off_y` | |
| **K** | Eckenradius der Platte (Radiuslehre oder Foto) | Radiuslehre | 0,0 | `K_corner_r` *(noch nicht verdrahtet)* | |
| **L** | Abstand Plattenunterseite bis zum Austritt der Kanüle aus dem Sockel (Höhe, die unter der Platte hervorsteht) | Tiefenmaß | 0,0 | `L_head_standoff` *(noch nicht verdrahtet; bestimmt später, ob der Boden eine Aussparung braucht)* | |
| **M** | Wie tief darf die 30G-Nadel ins Septum (Septumdicke, von der Plattenoberseite) | Septumdicke messen, 0,1 mm Reserve abziehen | 1,9 | `M_needle_depth` | |
| **N** | Gewünschtes Spiel Tasche-zu-Platte (je Seite) | – (Designentscheidung, MJF 0,2 / SLA 0,15) | 0,2 | `N_clearance` | |

Zusätzlich bitte notieren (für die spätere Verfeinerung der Tasche):

1. Rastet der Kopf mit einem **Klick** ein, und in welche Richtung wird er eingeschoben (von oben auf die Platte / seitlich)?
2. Foto der Platte von oben, von der Seite und von unten (mit Maßstab / Münze daneben).
3. Misst das Septum **plan** zur Plattenoberfläche oder liegt es vertieft (Tiefe in mm)?
4. Material/Härte der Flügel (flexibel, wie viel Federweg bis zum Lösen? Zusammendrücken um ca. ___ mm).

## Nach dem Messen

1. Werte in `mechanical/params.json` unter `"cannula"` eintragen.
2. `python3 generate.py && python3 check.py` ausführen (siehe README.md).
3. Probedruck **nur der Aufnahmetasche** (Ausschnitt, ca. 20 x 20 mm) mit 3 Spielvarianten
   (`N_clearance` = 0,10 / 0,15 / 0,20) und am echten Kopf Schnappgefühl prüfen – bevor der ganze Pod gedruckt wird.

Hinweis: Das Modell geht von **Schnappflügeln an den beiden X-Seiten** der Platte aus (Nuten in den
Taschenwänden bei ±A/2). Sitzen die Flügel in Wirklichkeit an den Y-Seiten oder an anderer Stelle,
bitte das Foto zurückmelden – dann wird die Tasche in `op_build.py` (`build_bottom`) umgebaut.
