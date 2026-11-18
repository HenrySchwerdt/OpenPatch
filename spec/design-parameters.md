# OpenPatch – Gemeinsame Design-Parameter (Single Source of Truth)

> Alle Teilprojekte (mechanical/, electronics/, firmware/, ios/) MÜSSEN diese Werte verwenden.
> Änderungen nur hier, dann in den Teilprojekten nachziehen.
> Status: Konzept v0.1 (2026-11-18). Experimentelles DIY-Gerät, KEIN zugelassenes Medizinprodukt.

## 1. Produktkonzept

- Wiederverwendbare, abnehmbare Patch-Pumpe ("Pod"), die direkt auf den Kanülenkopf eines
  **Accu-Chek Insight Flex** Infusionssets (Roche, 6/8/10 mm) aufgesteckt wird – kein Schlauch.
- Befestigung am Körper: Klett (Hakenseite am Pod-Boden, Flauschseite auf medizinischem Pflaster
  um die Kanüle) – der Pod ist abnehmbar (Duschen, Sport), Kanüle bleibt.
- Befüllung mit Spritze durch ein Silikon-Septum (wie Omnipod), Insulin U100.
- Induktiv ladbar (kein Steckerloch → einfacher wasserdicht).
- Drei Varianten, die sich NUR in der Reservoir-/Gehäuselänge unterscheiden: **70 IE, 100 IE, 200 IE**.

## 1a. Montage ohne Lötkolben (Anforderung)

- Alle Elektronik wird von PCBWay bestückt; Akku und Motor werden über **SMD-Federkontakte (≤ 1,2 mm)** kontaktiert, die der Deckel anpresst.
- Qi-Spule: Leiterbahnspule auf der Platine oder von PCBWay bestückt.
- Gehäuse: Schrauben/Schnapphaken; Werkzeug: Pinzette, kleiner Schraubendreher, UV-Lampe.

## 2. Hüllmaße (Ziele)

| Größe | Volumen U100 | Ziel L × B × H (mm) | Omnipod DASH zum Vergleich |
|---|---|---|---|
| OP-70  | 0,70 ml | **38,0 × 32 × 8,5** (CAD ✓) | 52 × 39 × 14,5 mm |
| OP-100 | 1,00 ml | **42,0 × 32 × 8,5** (CAD ✓) | |
| OP-200 | 2,00 ml | **55,4 × 32 × 8,5** (CAD ✓) | |

- **Bauhöhe 8,5 mm** (8,0 ist mit 16×5-Reservoir nicht erreichbar: Stack = 8,4 mm; nur mit 0,6 mm Reservoirwand + 0,75 mm Schale) inkl. Gehäusewand und Klett-Fläche. Ecken R ≥ 4 mm, Oberseite leicht gewölbt (Kissen-Form).
- Wandstärke Gehäuse: 0,9 mm (MJF PA12 oder SLA-Resin für Prototyp; später Spritzguss PC/PP).

## 3. Reservoir (flach, „Stadion“-Querschnitt)

- Starres Reservoir mit **Stadion-Querschnitt (Langloch) 16,0 × 5,0 mm innen** → Fläche A = 5·11 + π·2,5² = **74,6 mm²**.
- Kolbenhub: 70 IE → 9,4 mm; 100 IE → 13,4 mm; 200 IE → 26,8 mm (+1,0 mm Totraum-Reserve).
- Reservoirwand 0,8 mm, Material: COC/PP (insulinverträglich). Prototyp: gekaufte Rohteile/CNC-PP oder SLA BioMed-Resin, **nur für Wassertests**.
- Kolben: PP-Kern mit eingegossener Silikon-/FKM-Lippendichtung (Stadion-Form) – größtes Entwicklungsrisiko, eigenes Testprogramm.
- Befüllseptum: Silikon Ø 4 mm × 2 mm, seitlich, mit Füllkanal ins Reservoir.
- Auslass: Kanal → Stahl-Hohlnadel 30G (Ø 0,31 mm), die in das Septum des Insight-Flex-Kanülenkopfs sticht.

## 4. Antrieb

- Micro-Schrittmotor **Ø 6 mm** (Ref.: Faulhaber ADM0620 / FDM0620, 2-phasig, 20 Schritte/U, 3 V) quer neben dem Reservoir.
- Stirnrad-/Planetenstufe **i = 10:1**, Gewindespindel **M1,6 × 0,35** (Messing/Edelstahl) **in einer eigenen Spur NEBEN dem Reservoir**; Mutter-Schlitten mit Arm, der durch einen Schlitz am Reservoirende den Kolben schiebt (inline wäre ~2× Hub Länge → 48/56/83 mm).
- Auflösung: 0,35 mm / (20·10) = 1,75 µm/Schritt → **0,131 µl/Schritt = 0,0131 IE/Schritt**.
- Kleinster Bolus-/Basalpuls: **0,05 IE ≈ 4 Schritte** (Ist-Wert 0,0524 IE; Firmware akkumuliert Rest).
- Spindel-Encoder: Magnet auf Spindel + Hall-Sensor (z. B. TMAG5273 / AS5600L-Klasse) zur **unabhängigen Förderverifikation**.
- Okklusionserkennung: Motorstrom/Back-EMF-Anstieg + Encoder-Schlupf (kein Weg trotz Schritten).

## 5. Elektronik

- MCU/BLE: **Nordic nRF54L15** (QFN48 6×6 mm; Fallback nRF52833 QFN40). Kein Custom-ASIC (bei PCBWay nicht fertigbar, Kosten >> 500 €).
- Motortreiber: **ST STSPIN220** (QFN 3×3, 1,8–10 V) oder TI DRV8834; **Motor-Enable hardwareseitig über zweiten Pfad gegated** (Sicherheits-Watchdog, siehe docs/02-safety.md).
- Unabhängiger Watchdog: TI **TPL5010** (externer Nano-Power-Timer) → schaltet Motor-Treiber-Versorgung ab, wenn nicht bedient.
- Akku: Li-Po flach, **max. 3,2 × 19,8 × 17,2 mm** (302020-Klasse, ca. 40–60 mAh; 302030 passt nicht), mit PCM.
- Laden: **Qi-Empfänger TI BQ51003** (2,5 W-Klasse) + Laderegler **BQ25120A** (oder MCP73832), Empfängerspule **Ø 17,6 mm flach (Ø20 kostet +2,4 mm Länge), auf Flex-PCB oder Würth 760308101xxx-Klasse**. Alternative später: NFC-WLC (ST25/PTX30W).
- Summer: Piezo-Buzzer 9 × 9 × 2 mm; Vibrationsmotor optional.
- Taster: 1× (Notfall-Stopp / Alarm-Quittierung), durch Gehäusemembran.
- PCB: 4-Lagen, 0,6 mm; Form: Rechteck mit L-Ausschnitt (Kontur aus mechanical/out/OP-xx.layout.json).
- Bauhöhe-Stack (vom Körper weg): Boden 0,9 | Akku 3,2 | PCB+Bauteile 1,6 | Deckel 0,9 → Rest Spule/Toleranz. Reservoir+Motor liegen in derselben Ebene wie Akku+PCB (nebeneinander, nicht gestapelt).

## 6. Funk / Protokolle

1. **OpenPatch-Protokoll (nativ)** – eigenes BLE-GATT-Profil, offen dokumentiert in `docs/04-protocol.md`, Trio-Integration über eigenes LoopKit-PumpManager-Kit `OpenPatchKit`.
2. **DASH-Kompatibilitätsmodus** – Pod-seitige Emulation des Omnipod-DASH-BLE-Protokolls, so dass Trio über das vorhandene `OmnipodKit` (loopandlearn) spricht. Referenz-Implementierung: `nightscout/ESP-Sim` (GPL-3.0 → Firmware-Teil dann GPL-3.0).
3. **Omnipod 5**: wird NICHT emuliert – O5-Pairing nutzt P-256/ECDSA-signierte Transkripte und einen externen Key-Manager mit App Attest; DASH-Modus deckt Trio ab.

Hinweis: Im DASH-Modus „sieht“ Trio einen 200-IE-Pod mit 80-h-Lebensdauer; Reservoir-Anzeige ab < 50 IE, wie bei DASH. Nativer Modus zeigt echte Werte, Akku, Wiederverwendbarkeit.

## 7. Sicherheitsgrenzen (Firmware-Defaults, hart kodiert als Obergrenzen)

- Max. Einzelbolus: 10 IE (konfigurierbar ≤ 25 IE)
- Max. Basalrate: 5 IE/h (konfigurierbar ≤ 30 IE/h)
- Max. Fördermenge / Stunde (gesamt): 15 IE
- Bolusgeschwindigkeit: 1,5 IE/min
- Okklusionsalarm: ≤ 2 IE nicht geförderte Menge
- Kommunikationsverlust: Temp-Basal läuft max. 30 min weiter, dann Rückfall auf programmierte Basalrate (DASH-Semantik)
- Encoder-Abweichung > 10 % über 1 IE → Förderstopp + Alarm

## 8. Kanülen-Schnittstelle (Insight Flex)

- Laut Roche-IFU: Schlauch wird auf die Konnektorplatte des Kanülenkopfs geschoben, Lösen durch Zusammendrücken zweier Seitenflügel → **Zwei-Flügel-Schnapphaken**, kein Luer.
- Genaue Geometrie ist **nicht öffentlich** → muss vom Nutzer mit Messschieber vermessen werden (Messblatt: `mechanical/cannula-measurement.md`). Bis dahin parametrischer Platzhalter im CAD:
  - Konnektorplatte (Annahme): 14 × 10 × 3,0 mm, Nadel-Eintritt mittig, Schnapp-Nut beidseitig 1,0 mm.
- Der Pod hat unten eine Aufnahmetasche, in die der Kanülenkopf einrastet; die 30G-Nadel durchsticht das Kanülen-Septum.
