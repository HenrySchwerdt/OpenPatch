# Patente & Stand der Technik

Recherche-Stand: 2026-11-18. **Keine Rechtsberatung.** Die Ablaufdaten stammen aus Google Patents, und Google kennzeichnet sie selbst als Schätzung. Durch Laufzeitverlängerungen (PTA/SPC) kann ein Patent später ablaufen als „Anmeldung + 20 Jahre“. Für den rein privaten, nicht gewerblichen Eigengebrauch gilt in Deutschland zusätzlich die Ausnahme aus § 11 Nr. 1 PatG. Auch das solltest du selbst prüfen.

## Was wir davon übernehmen (abgelaufen → frei nutzbar)

| Patent | Inhaber | Status | Idee, die wir nutzen |
|---|---|---|---|
| [US6740059B2](https://patents.google.com/patent/US6740059B2/en) | Insulet | abgelaufen 2021 | Reservoir 2–3 ml, Befüllung mit Spritze durch ein selbstdichtendes Silikon-Septum |
| [US6656159B2](https://patents.google.com/patent/US6656159B2/en) | Insulet | abgelaufen 2022 | Spindelantrieb mit Rücklaufsperre; feste Pulsgröße 0,5 µl (= 0,05 IE) |
| [US7250037B2](https://patents.google.com/patent/US7250037B2/en) | BD | abgelaufen 2025 | flaches Reservoir: starre, gewölbte Schale mit Folie (Alternative zu unserem Stadion-Reservoir) |
| [US4781688](https://patents.google.com/patent/US4781688) | – | abgelaufen | komprimierbares, flexibles Reservoir |

## Wahrscheinlich noch in Kraft → umgehen oder Alternative wählen

| Patent | Inhaber | Kern | Unsere Abgrenzung |
|---|---|---|---|
| [US7935104B2](https://patents.google.com/patent/US7935104B2/en) (bis ca. 2029) | Medingo → Roche (Accu-Chek Solo) | Wiederverwendbarer Teil mit Motor und Elektronik, Einwegteil mit Batterie, Beutel und Peristaltik | Bei uns ist **alles** im wiederverwendbaren Pod, inklusive Akku und starrem Kolbenreservoir. Einweg ist nur die gekaufte Kanüle. Kein Peristaltik-Antrieb. |
| [US7771392](https://patents.google.com/patent/US7771392) | Roche/Disetronic | Ein SMA-Draht treibt zwei Ratschenräder | Wir nutzen einen Schrittmotor statt SMA |
| [US8535269B2](https://patents.google.com/patent/US8535269B2/en) (bis ca. 2029) | Roche | Insertionskopf mit Nadelschutz im Griff (vermutlich Insight-Flex-Familie) | Wir **kaufen** die Kanüle und stecken nur an. Den Kopf bauen wir nicht nach. |
| Tandem [US12661446B2](https://mtec-sc.org/patents/US-12661446-B2) | Tandem | Kartusche wird schräg eingesetzt und durch Drehen verriegelt, Encoder an der Spindel | Encoder allein ist Stand der Technik; die Verriegelungsgeometrie übernehmen wir nicht |
| EOFlow, CeQur, SteadyMed (elliptisches Reservoir [US10112005](https://patents.justia.com/patent/10112005)) | div. | Elektroosmose, Druckquelle mit Drossel, **nicht-runde Reservoire** | ⚠️ Unser Stadion-Reservoir liegt in der Nähe von SteadyMed (elliptisch) und US11980739 (nicht-runder Kolben). Vor einer Veröffentlichung oder einem Verkauf die Ansprüche genau lesen. Fallback: BD-Folienreservoir (abgelaufen). |

## Okklusionserkennung

Medtronic hält dazu mehrere Patente, z. B. [US7892206](https://patents.justia.com/patent/7892206) (mittlerer Motorstrom) und [US8864739](https://patents.google.com/patent/US8864739) (Kraft × Strom). Ältere Varianten wie [US2001/0034502](https://patents.justia.com/patent/20010034502) aus dem Jahr 2001 sind abgelaufen. Wir verwenden **Encoder-Schlupf** (Schritte ohne gemessene Spindeldrehung) und einen einfachen Stromschwellwert. Beides ist alter Stand der Technik.

## Accu-Chek Insight Flex – Schnittstelle

- Laut [IFU](https://www.accu-chek.co.uk/document/accu-chek-insight-flex-instructions-use/download) besteht das Set aus Kopf („Kanüle“) und Schlauch. Der Schlauch wird auf die Konnektorplatte gesteckt und durch Zusammendrücken der Seitenflügel wieder gelöst. Es ist **kein Luer-Anschluss**. Nach jedem Ankoppeln wird mit 0,7 IE gefüllt („Kanülen-Priming“).
- Maße, CAD-Modelle und Teardowns sind **nicht öffentlich**. Die Geometrie musst du vermessen, siehe `mechanical/cannula-measurement.md`.
- Konsequenz für die Firmware: Bei **jedem Wiederanstecken** des Pods 0,7 IE Kanülen-Priming anbieten. Wer den Pod oft abnimmt, verliert dadurch Insulin.

## Weitere Referenzen

- Teardown des Omnipod-Antriebs: [Hackaday 2023](https://hackaday.com/2023/04/25/insulin-pump-teardown-shows-one-motor-does-many-jobs), [Lumafield](https://lumafield.com/de/scan-of-the-month/health-wearables)
- Open-Source-Pumpe (Spritzenpumpe, HardwareX 2022): [UCBioengineering/open_source_insulin_pump](https://github.com/UCBioengineering/open_source_insulin_pump)
- Piezo-Mikropumpen (Bartels mp6): Für Insulin gibt es keine Validierung. Fraunhofer EMFT berichtet bei Insulin Dosierfehler durch Blasenbildung ([Link](https://emft.fraunhofer.de/en/projects-fraunhofer-emft/study-optimized-insulin-dosing-micropumps.html)). → Deshalb verwenden wir einen Kolbenantrieb.
- Medtrum TouchCare Nano (wiederverwendbare Basis, 200 IE): 40,5 × 31,5 × 11,5 mm, 13,8 g. Das ist unser realistischer Benchmark für die Größe.
