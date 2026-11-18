# Kostenschätzung: 5 bestückte OP-100-Boards bei PCBWay (Rev A)

> Stand 2026-11-18. **Alle PCBWay-Preise sind Schätzungen**: Eine verbindliche Zahl gibt nur das PCBWay-Online-Quote mit der echten BOM. Gefunden wurde nur: Teilepreise bei LCSC/DigiKey (Websuche), „Setup-Gebühr 88 – 150 USD“ und „10 – 30 % Aufschlag auf Bauteile“ aus nicht verifizierbaren Drittquellen, Faulhaber nennt für DM0620 „Preis auf Anfrage“. Währung EUR, Netto, Einfuhr-USt 19 % (DE) nicht enthalten (Zeile unten).

## Annahmen

* 5 Boards, 4 Lagen, 0.6 mm, ENIG, Platine 17.1 × 29 mm mit Ecken-Aussparung (laut mechanical/out/OP-100.layout.json; kleine Fläche = kaum Preisvorteil, Fixkosten dominieren), Panel/Array nach PCBWay.
* Turnkey (PCBWay beschafft): ~42 Positionstypen, ~75 Bestückungen/Board (kein QFN48/Quarze/RF-Netz mehr dank Modul), 2-seitig, 3 WCSP/DSBGA (BQ51003, BQ25120A, TPS22916C), 1 LGA-78-Modul (ISP1807, 0.65 mm), X2SON, 0402.
* Von Hand/separat: Qi-Spule, LiPo, Motor, Magnete, Gehäuse (nicht PCBWay-SMT).
* Teilepreise/Board aus `bom.csv`: SMT-Teile inkl. Piezo/Taster **20.20 EUR** (davon ISP1807-Modul ~10.3 EUR, Preis @1 ~11.2 USD aus LCSC/Mouser-Listing), Spule 4.00 EUR.

## Positionen (5 Boards)

| Posten | Low | Mittel | High | Anmerkung |
|---|---:|---:|---:|---|
| Leiterplatte 4L 0.6 mm ENIG, 5 Stk | 35 | 45 | 70 | 0.6 mm + ENIG + 4L/Via-in-Pad (0.4-mm-BGA) kann Aufpreis kosten |
| Bestückungs-Setup | 60 | 85 | 150 | Drittquelle: 88–150 USD |
| Schablone | 0 | 15 | 25 | teils inklusive |
| Bestückung/Löten (75 Teile × 5, 2 Seiten, 3 BGA-Typen + LGA/X-Ray) | 55 | 110 | 190 | größter Unsicherheitsfaktor |
| Bauteile 5 × 20.20 + Mindestmengen + Aufschlag 20 % | 120 | 150 | 215 | 0402-Rollenmengen (MOQ), Sonderteile ohne LCSC-Nr. (ISP1807 evtl. Kundenbeistellung, U6, U7, U9/10, Q2, D1/D2, L4) über DigiKey/Mouser |
| Versand PCBWay → DE (DHL/UPS) | 25 | 35 | 45 | |
| **Zwischensumme Platinen** | **265** | **415** | **665** | |
| Qi-Spulen Ø17.6 (Flex-PCB-Spirale/Rx-Spule) 6 × 4 | 15 | 24 | 40 | Flex-Spirale bei PCBWay oder Spezialspule; Typ unverifiziert (Würth 760308101104 ist TX!) |
| LiPo Sonderformat ≤ 3.2 × 17.4 × 17.2 mm (~40 mAh) + PCM, 6 Stk | 15 | 21 | 40 | 302020 (20 × 20) passt im OP-100-Layout nicht (Länge auf 17.4 mm begrenzt) → Sonderformat/MOQ |
| Magnete Ø2 × 1 diametral | 3 | 4 | 8 | |
| **3 Gehäusesätze (PCBWay SLA/MJF)** | 40 | 60 | 110 | je Satz Körper + Deckel + Reservoirschale; MJF PA12 ~12–20 EUR/Satz, SLA-Resin ähnlich, + Versand/Mindestauftrag |
| Kleinteile (Silikon-Septum, 30G-Nadel, Kleber, Schrauben, Litze) | 20 | 30 | 40 | |

## Motoren – beide Preisvarianten

| Variante | Stückpreis | 6 Stk (5 + 1 Reserve) | Bemerkung |
|---|---:|---:|---|
| **A: generischer Ø6 mm 2-Phasen-Stepper + Planetengetriebe + Spindel** (AliExpress/eBay/Fruugo-Klasse) | ~6 – 12 EUR (Mittel 9) | **36 / 54 / 72** | Stepper allein 1–5 EUR (eBay-Funde, 0.99–4.98 USD), mit Getriebe+Spindel+Versand ~8–12 EUR. Kein passender Datenblatt-Nachweis für 20 Schritte/U, Drehmoment, Lebensdauer – Streuung/Spiel hoch → Encoder-Verifikation Pflicht. Namiki-Mikromotoren: keinen verifizierbaren Preis gefunden. |
| **B: Faulhaber ADM0620/DM0620-Klasse** | 60 – 120 EUR (Mittel 90, **geschätzt**, nur „Preis auf Anfrage“ gefunden) | **360 / 540 / 720** | Referenz der Spec; nur sinnvoll für das erste validierte Funktionsmuster (1–2 Stück) |

## Gesamtbild

| | Low | Mittel | High |
|---|---:|---:|---:|
| Platinen (Zwischensumme) | 265 | 415 | 665 |
| Spule + LiPo + Magnete | 33 | 49 | 88 |
| Gehäuse + Kleinteile | 60 | 90 | 150 |
| **Summe ohne Motoren** | **358** | **554** | **903** |
| + Motoren A (günstig) | 36 | 54 | 72 |
| **Gesamt mit Motoren A** | **394** | **608** | **975** |
| + Motoren B (Faulhaber) statt A | 360 | 540 | 720 |
| **Gesamt mit Motoren B** | **718** | **1094** | **1623** |


## Passt das in 500 EUR?

**Ehrlich: knapp nicht im Mittelfall.** Mit günstigen Motoren (A) liegt der Mittelwert bei ~608 EUR (netto), im optimistischen Fall ~394 EUR; mit Faulhaber-Motoren (B) ist das Budget klar gesprengt (>700 EUR).

Hebel, um unter 500 EUR zu kommen (zusammen etwa −120 … −170 EUR):

1. **Rev A ohne Qi:** BQ51003 + Spule + ~15 Passive (inkl. 0805-C0G ×3) weglassen, Laden über Pogo-/Federkontakt-Pads an VQI_5V (TP8) → −10 EUR Bauteile/Board, weniger BGA-Aufwand, ca. **−60 … −90 EUR**. Qi dann in Rev B auf eigenem Testboard entwickeln (Spulenabstimmung ist ohnehin Handarbeit).
2. **Einseitig bestücken** (Bestückungs-Setup/Arbeit −30 … −60 EUR), Piezo/Akku-Pads/Q1 auf Oberseite; die Fläche im Arm ist knapp, ein 2-lagiges Re-Floorplan nötig.
3. **3 statt 5 Boards:** spart nur Bauteile/Versand (~−25 EUR) – Fixkosten dominieren, daher kaum Gewinn.
4. **Nur 1 Gehäusesatz in MJF, 2 in billigem SLA** (−20 EUR); **LiPo/Spule aus Elektronik-Schrott** für Bench-Tests.
5. **Motoren A für Serie, Faulhaber nur 1 Muster** (Anfrage über Micromo/Distributor, Preis sichern).

Mit den Hebeln 1 + 2 + 4 ergibt sich im Mittelfall ≈ **440 – 500 EUR** (Variante A), ohne USt. **Unsicherheit der PCBWay-Zahlen ±30 %.**

**Modul-Entscheidung:** Der ISP1807 (~10.3 EUR/Stk) ersetzt nRF54L15 (~3.9 EUR) + Quarze + Antenne + HF-Netz (~5 EUR) → Mehrkosten ~1.5 EUR/Board (~8 EUR bei 5 Boards), dafür kein RF-Layout/-Tuning, ein CE-/FCC-vorqualifiziertes Funkteil und weniger Bestückungen. Preisrisiko: LCSC-Lagerbestand 0, Lieferzeit ~4 Wochen bei DigiKey.

## Empfohlene Reihenfolge

1. BOM in PCBWay-Quote hochladen (DXF + Gerber nach Layout) → echten Preis für Setup, BGA-Fee und Teile holen, Positionen ohne LCSC-Nr. markieren.
2. Zuerst Hardware-Spike auf Dev-Boards: nRF54L15 DK + STSPIN220-Breakout + billiger Ø6-Motor + TPL5010-Breakout testen (Sicherheitspfad und Encoder) – etwa 80 – 120 EUR, bevor 400+ EUR in Platinen fließen.
3. Dann Rev A (ggf. ohne Qi).
