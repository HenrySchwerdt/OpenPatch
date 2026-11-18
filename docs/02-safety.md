# Sicherheitskonzept

> **Wichtig:** OpenPatch ist ein experimentelles DIY-Gerät und kein zugelassenes Medizinprodukt. Fehlförderung von Insulin kann tödlich sein: Hypoglykämie bei Überförderung, Ketoazidose bei Unterbrechung. Benutzung auf eigenes Risiko. Halte immer Pen oder Spritze, Glukagon und einen CGM-Alarm bereit.

## 1. Gefährdungen und Gegenmaßnahmen

| # | Gefährdung | Ursache | Gegenmaßnahme (Ebene) |
|---|---|---|---|
| H1 | **Überförderung** | Firmware-Bug, Motor läuft durch, BLE-Kommando doppelt, Kolben „springt“ | (a) Safety-Supervisor mit harten Grenzen, getrennt von der Delivery-Engine (FW). (b) Motortreiber braucht **zwei** Freigaben: MCU-GPIO **und** externer Watchdog TPL5010 (HW). (c) Encoder misst die tatsächliche Spindeldrehung unabhängig von den Schritten (HW+FW). (d) Sequenznummern und Replay-Schutz (Protokoll). (e) Stündliches Rolling-Limit von 15 IE. |
| H2 | **Unterförderung / Okklusion** | Kanüle abgeknickt, Pod nicht eingerastet, Luft | Encoder-Schlupf, Stromanstieg, Alarm ab ≤ 2 IE nicht gefördert; Erkennung des Andockens (Hall- oder Kontaktschalter in der Kanülentasche) |
| H3 | **Unbemerkter Förderstopp** | Akku leer, Brown-out, Absturz | Akku-Warnung bei 20 %, Alarm bei 10 %; Brown-out-Reset → Pod startet im Zustand **SUSPENDED** und meldet sich mit Alarm, statt still weiterzulaufen; Summer läuft aus einem eigenen Pfad |
| H4 | **Luft im Reservoir** | Befüllung | Füllanleitung mit Entlüften, Priming-Pflicht vor dem ersten Ankoppeln |
| H5 | **Falsche Konzentration** | U200 statt U100 | App verlangt beim Füllen U100 und Insulintyp |
| H6 | **Kommunikationsverlust** | BLE weg | Temp-Basal fällt nach max. 30 min auf die programmierte Basalrate zurück; Basal läuft autark auf dem Pod weiter |
| H7 | **Fremdzugriff** | Angreifer per BLE | Pairing mit Schlüsselaustausch (X25519), AES-CCM, kein unauthentifiziertes Bolus-Kommando, Pairing nur nach Tastendruck am Pod |
| H8 | **Insulin-Degradation** | Wärme durch Laden oder Elektronik, ungeeignete Materialien | Laden nur mit abgenommenem Pod (Ladeerkennung → Förderung pausiert + Hinweis); Temperatursensor; insulinberührte Teile nur aus PP/COC/Silikon in Medizinqualität. **3D-Druck-Reservoire nur für Wassertests.** |
| H9 | **Abnehmen vergessen / Pod am Ladegerät** | Benutzung | Andock-Erkennung: Ist der Pod nicht angedockt, pausiert er die Förderung, alarmiert nach 15 min und meldet „nicht angekoppelt“ an Trio |
| H10 | **Mechanischer Rücklauf / Siphon** | Druck auf das Gehäuse | Stadion-Kolben mit Verdrehsicherung, selbsthemmende Spindel (M1,6 × 0,35 ist selbsthemmend) |

## 2. Hardware-Interlock (Kern)

```
            MCU GPIO MOTOR_EN ──┐
                                 AND ──► Load-Switch ──► STSPIN220 VS/VDD
 TPL5010 WAKE/DONE-Watchdog ────┘
       (wird nur von der Safety-Task "gefüttert";
        bleibt sie aus → Motorversorgung hart AUS)
```

- Die Delivery-Engine darf **nie** selbst den Watchdog bedienen. Das tut ausschließlich der Safety-Supervisor, und nur, wenn alle Prüfungen bestanden sind.
- Die Encoder-Auswertung läuft im Safety-Supervisor. Weichen Schritte und Drehung um mehr als 10 % über 1 IE voneinander ab, folgt der Förderstopp.

## 3. Verifikationsplan vor dem ersten Einsatz am Körper

1. Gravimetrische Fördergenauigkeit mit Wasser auf einer Feinwaage mit 0,1 mg Auflösung: 0,05 / 0,5 / 5 IE, je 50 Wiederholungen. Ziel: ±5 % ab 1 IE.
2. Okklusionstest: Auslass verschlossen → Alarm vor 2 IE.
3. 72-h-Dauertest mit Wasser und Basalprofil, dabei BLE-Ab- und Wiederverbindungen.
4. Fehlerinjektion: Firmware hängt → Watchdog schaltet den Motor ab (oszilloskopisch prüfen).
5. Dichtheit: 30 min unter Wasser in 1 m Tiefe (IPX7-ähnlich).
6. Erst dann Tests mit Insulin, zunächst parallel zu einer zugelassenen Pumpe oder zum Pen, mit engmaschiger CGM-Überwachung.
