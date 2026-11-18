# OpenPatch-Protokoll v1 (nativ)

> Status: Entwurf v1, passend zu `firmware/core` (Stand 2026-11-18).
> **Experimentelles DIY-Gerät, kein Medizinprodukt.** Die Referenzimplementierung
> (`core/src/openpatch_*.c`) und diese Spezifikation müssen synchron bleiben;
> die Beispiel-Frames unten sind als Tests hinterlegt (`tests/test_proto.c`).

Einheiten: **mU** = Milli-Einheit (0,001 IE), Raten in **mU/h**. 1 Motorschritt = 0,0131 IE = 13,1 mU.
Alle Mehrbyte-Werte sind **little-endian**.

## 1. GATT-Profil

Zufällig erzeugte 128-Bit-Basis-UUID (einmalig, UUIDv4, nicht ändern):

```
2E092A48-506C-477E-ADD4-448BF149xxxx
```

Die letzten 16 Bit (`xxxx`) wählen Service bzw. Characteristic:

| Element | UUID | Eigenschaften | Zweck |
|---|---|---|---|
| Service | `2E092A48-506C-477E-ADD4-448BF1490001` | – | OpenPatch-Service |
| Command | `2E092A48-506C-477E-ADD4-448BF1490002` | Write, Write Without Response | Phone → Pod, genau ein Frame pro Write |
| Response | `2E092A48-506C-477E-ADD4-448BF1490003` | Notify | Pod → Phone, genau ein Frame pro Notification |
| Alert | `2E092A48-506C-477E-ADD4-448BF1490004` | Notify | reserviert für v1.x (ungefragte Alarme); in v1 nicht implementiert, Alarme werden per `GetStatus` gelesen |

Randbedingungen:

- Ein Frame ist höchstens **244 Byte** (`OP_FRAME_MAX` = ATT-MTU 247 − 3). Das Phone muss vor dem ersten Befehl einen MTU-Austausch auf ≥ 247 durchführen; es gibt keine Fragmentierung im Protokoll.
- Advertising: Gerätename `OpenPatch-XXXX` (letzte 4 Hex-Stellen der Adresse), Service-UUID im Advertising-Paket. Keine Nutzdaten im Advertising.
- Transport: BLE LE Secure Connections mit Bonding (Link-Layer-Verschlüsselung) **zusätzlich** zur Anwendungsschicht-Verschlüsselung (Abschnitt 5).

## 2. Frame-Format

```
Offset  Größe  Feld
0       1      version   = 0x01
1       1      type      Befehls-ID (Antwort: Befehls-ID | 0x80)
2       1      flags     Bit0 = verschlüsselt, Bit1 = Antwort
3       2      seq       Sequenznummer (LE)
5       2      len       Länge des Payloads in Byte (LE)
7       len    payload   TLV-Liste (bzw. Chiffretext || 8-Byte-Tag)
7+len   2      crc16     CRC-16/CCITT-FALSE über Byte 0 … 7+len-1 (LE)
```

- **CRC-16/CCITT-FALSE**: Polynom 0x1021, Startwert 0xFFFF, keine Spiegelung, kein Final-XOR. Prüfwert `"123456789"` → `0x29B1`.
- Gesamtlänge = 9 + len, höchstens 244. Der Empfänger prüft in dieser Reihenfolge: Mindest-/Maximallänge und `len`-Konsistenz (`OP_ERR_FRAME`), CRC (`OP_ERR_CRC`), Version (`OP_ERR_VERSION`).
- Frames mit Fehlern werden **ohne Antwort verworfen**; der Pod verändert dabei keinen Zustand.
- Die CRC schützt nur gegen Übertragungsfehler; Integrität/Authentizität gegen Angreifer stellt AES-CCM sicher (Abschnitt 5).

### 2.1 TLV-Payload

```
tag (u8) | length (u8) | value (length Byte)
```

- Unbekannte Tags werden **übersprungen** (Vorwärtskompatibilität). Ein abgeschnittenes TLV macht das Frame ungültig (`OP_ERR_FRAME`).
- Feste Längen je Tag (siehe Tabelle); falsche Länge → `OP_ERR_FRAME`.
- Tags anderer Befehle im selben Frame werden ignoriert.

## 3. Befehle

| ID | Name | Request-Tags | Response (zusätzlich zu `RESULT`) |
|---|---|---|---|
| 0x01 | GetStatus | – | alle Status-Tags (0x10–0x19, 0x09, 0x0E) |
| 0x02 | SetBasalSchedule | 1–24 × `BASAL_SEG` | – |
| 0x03 | SetTempBasal | `RATE_MU_H`, `DURATION_MIN` (beide Pflicht) | – |
| 0x04 | CancelTempBasal | – | – (`NOT_FOUND`, wenn keine aktiv) |
| 0x05 | Bolus | `AMOUNT_MU` (Pflicht) | – |
| 0x06 | CancelBolus | – | – (`NOT_FOUND`, wenn keiner aktiv) |
| 0x07 | Suspend | – | – |
| 0x08 | Resume | – | – (`FAULT`, solange ein Fehler gelatcht ist) |
| 0x09 | Fill/Prime | `SUB_OP` (1 = Fill, 2 = Prime) + `FILL_MU` bzw. `PRIME_STEPS` | – |
| 0x0A | Acknowledge | `FAULT_MASK` (optional, Standard 0xFFFF) | – |
| 0x0B | GetHistory | `FROM_ID` (opt., Standard 0), `MAX_EVENTS` (opt., Standard 10) | `NEXT_EVENT_ID`, `OLDEST_EVENT_ID`, 0–10 × `HISTORY_EVENT` |

Jeder Befehl darf zusätzlich `TIME_OF_DAY_MS` (u32, lokale Millisekunden seit Mitternacht) enthalten; der Pod
übernimmt die Uhrzeit für den Basalplan. Das Phone sendet sie mindestens bei `SetBasalSchedule` und nach jedem Verbindungsaufbau.

Antwort: gleiche `seq`, `type | 0x80`, Flag „Antwort“, erster Tag immer `RESULT` (u8, Fehlercodes Abschnitt 4).
Unbekannte Befehls-IDs werden mit `RESULT = UNSUPPORTED` beantwortet, fehlerhafte TLVs mit `RESULT = FRAME`.

### 3.1 Tag-Tabelle

| Tag | Name | Typ | Bedeutung |
|---|---|---|---|
| 0x01 | RESULT | u8 | Fehlercode (0 = OK) |
| 0x02 | BASAL_SEG | u8 start_slot, u16 rate | Segment; Slot 0–47 (30 min); erstes Segment Slot 0; streng aufsteigend; Segment endet beim nächsten Start bzw. um Mitternacht |
| 0x03 | RATE_MU_H | u16 | Temp-Basalrate in mU/h |
| 0x04 | DURATION_MIN | u16 | Temp-Dauer, Vielfaches von 30, 30…720 |
| 0x05 | AMOUNT_MU | u32 | Bolusmenge, Vielfaches von 50 mU (0,05 IE) |
| 0x06 | FILL_MU | u32 | eingefüllte Insulinmenge in mU |
| 0x07 | PRIME_STEPS | u16 | Prime-Schritte, 1…40 |
| 0x08 | SUB_OP | u8 | 1 = Fill (Füllmenge melden), 2 = Prime |
| 0x09 | FAULT_MASK | u16 | Fehlerbits (Abschnitt 4.1) |
| 0x0A | FROM_ID | u32 | History ab dieser ID (einschließlich) |
| 0x0B | MAX_EVENTS | u8 | max. Events pro Antwort (0 oder > 10 → 10) |
| 0x0C | TIME_OF_DAY_MS | u32 | lokale Uhrzeit, optional bei jedem Befehl |
| 0x0D | HISTORY_EVENT | 17 B | `u32 id, u32 time_s, u8 type, i32 a, i32 b` |
| 0x0E | NEXT_EVENT_ID | u32 | ID des nächsten (noch nicht vergebenen) Events |
| 0x0F | OLDEST_EVENT_ID | u32 | älteste noch gespeicherte ID |
| 0x10 | STATE_FLAGS | u16 | Bit0 Suspended, 1 Bolus aktiv, 2 Temp aktiv, 3 Basalplan vorhanden, 4 Reservoir niedrig, 5 Alarm, 6 befüllt, 7 Akku niedrig |
| 0x11 | RESERVOIR_MU | u32 | verbleibende Menge (konservativ abgerundet) |
| 0x12 | BATTERY_MV | u16 | Akkuspannung |
| 0x13 | BOLUS_REMAINING_MU | u32 | noch nicht geförderter Bolusanteil |
| 0x14 | TEMP_RATE_MU_H | u16 | 0, wenn kein Temp aktiv |
| 0x15 | TEMP_REMAINING_MIN | u16 | aufgerundet |
| 0x16 | CURRENT_RATE_MU_H | u16 | aktuell gültige Basalrate (Temp oder Plan) |
| 0x17 | DELIVERED_MU | u32 | seit Boot geförderte Menge (aus Schritten) |
| 0x18 | SCHEDULED_MU | u32 | seit Boot programmierte Menge (zeigt Defizit bei Suspend/Veto) |
| 0x19 | FW_VERSION | u16 | `major<<8 \| minor` |

`GetStatus` trägt `FAULT_MASK` (0x09) als aktuell gelatchte Fehler und `NEXT_EVENT_ID` (0x0E) als nächste Event-ID.

### 3.2 Semantik (DASH-nah)

- Nach dem Einschalten ist der Pod **suspendiert**; erst `Resume` startet die Basalabgabe.
- Bolusgeschwindigkeit 1,5 IE/min. Während eines Bolus ruht die Basalabgabe, ohne Nachholen.
- `Suspend` bricht Bolus und Temp-Basal ab; `Resume` kehrt zur programmierten Basalrate zurück.
- **Kommunikationsverlust**: jeder authentifizierte, frische Befehl setzt den Timer zurück. 30 min nach dem letzten Befehl fällt ein laufendes Temp-Basal auf den programmierten Basalplan zurück (Event `TEMP_COMM_FALLBACK`). Boli sind nicht betroffen (sie dauern max. 17 min bei 25 IE).
- `Fill` ist nur im suspendierten Zustand erlaubt (`NOT_SUSPENDED` sonst), setzt den Reservoirstand und den Encoder-Bezugspunkt. `Prime` (nur suspendiert, max. 40 Schritte ≈ 0,52 IE) fördert Insulin über den Sicherheitsüberwacher und wird per Encoder verifiziert. **Prime nur bei abgenommenem Pod.**
- `Acknowledge` quittiert gelatchte Fehler. Es startet **nie** automatisch die Abgabe (danach explizit `Resume`). Fehler, deren Ursache anhält (Akku kritisch, Reservoir leer), bleiben gelatcht (`PERSISTS`).

## 4. Fehlercodes und Fehlerbits

| Code | Name | Bedeutung |
|---|---|---|
| 0 | OK | |
| 1 | BAD_ARG | Wert ungültig (Raster 0,05 IE, Dauer, Segmentreihenfolge …) |
| 2 | LIMIT | über Max-Bolus/Max-Basal (konfigurierbar, harte Obergrenzen 25 IE / 30 IE/h) |
| 3 | BUSY | Bolus läuft bereits |
| 4 | FAULT | Fehler gelatcht |
| 5 | SUSPENDED | Abgabe suspendiert |
| 6 | NOT_SUSPENDED | Befehl nur im suspendierten Zustand erlaubt |
| 7 | RESERVOIR | Menge übersteigt Reservoirinhalt / nicht befüllt |
| 8 | PERSISTS | Ursache des Fehlers besteht noch |
| 9 | UNSUPPORTED | unbekannter Befehl |
| 10 | FRAME | fehlerhaftes Frame/TLV |
| 11 | CRC | (nur lokal, es wird nicht geantwortet) |
| 12 | VERSION | (nur lokal) |
| 13 | REPLAY | (nur lokal) |
| 14 | AUTH | (nur lokal) |
| 15 | TOO_LARGE | Puffer/Frame zu groß |
| 16 | HOURLY | Bolus würde die 15-IE-Stunden-Grenze verletzen |
| 17 | NOT_FOUND | nichts zu stornieren |
| 18 | SESSION | Sequenzraum erschöpft, neuer Schlüssel nötig |

### 4.1 Fehlerbits (`FAULT_MASK`)

| Bit | Name | Auslöser |
|---|---|---|
| 0 | OCCLUSION | (befohlen − encoder-bestätigt) > 2 IE, oder Spindel steht trotz Schritten |
| 1 | ENCODER_DEVIATION | Abweichung > 10 % über ein Fenster von ≥ 1 IE |
| 2 | RESERVOIR_EMPTY | Reservoir leer oder Schritt vom Reservoirmodell vetoiert |
| 3 | BATTERY_CRITICAL | < 3,3 V (Annahme, in `op_types.h` anpassbar) |
| 4 | LIMIT_EXCEEDED | Veto durch 15-IE/h-Fenster oder Minuten-Backstop (130 Schritte/min) |
| 5 | INTERNAL | Motor hat freigegebene Schritte nicht ausgeführt |

Gelatchte Fehler stoppen sofort jede Abgabe, aktivieren den Alarm-Summer und das Treiber-Enable-Gate. Quittierung nur per `Acknowledge`.

## 5. Sicherheit

### 5.1 AES-CCM (Schnittstelle, Platzhalter)

Mit Flag `verschlüsselt` besteht der Payload aus `Chiffretext || Tag` (Tag = 8 Byte, AES-128-CCM, L = 2).

- **AAD** = die 7 Header-Bytes (inkl. `type`, `flags`, `seq`, `len`) → Header kann nicht manipuliert werden.
- **Nonce (13 Byte)** = `salt[4] ‖ dir[1] ‖ seq[2, LE] ‖ 0x00 × 6`; `dir` = 0 für Befehle, 1 für Antworten; `salt` stammt aus der Schlüsselvereinbarung der Sitzung.
- Die Schnittstelle (`op_ccm_ops_t` in `openpatch_proto.h`) kapselt `encrypt`/`decrypt`; die echte Implementierung (nRF54L15 CRACEN oder PSA Crypto) wird später eingehängt. **Im Repository existiert nur eine unsichere Test-Attrappe** (`tests/fake_ccm.c`); sie darf nie in Firmware gelangen.
- Produktion: `allow_plaintext = false`. Klartext-Frames werden dann mit `AUTH` verworfen.
- Antwortframes verwenden die Befehls-`seq` mit `dir = 1`; dadurch wird nie ein Nonce doppelt benutzt.

### 5.2 Replay-Schutz

- Befehls-`seq` müssen **streng monoton steigen** (Lücken erlaubt). Gleiche oder kleinere Werte → `REPLAY`. Der Zustand wird erst nach erfolgreicher Authentifizierung fortgeschrieben, damit Fälschungen den Zähler nicht verbrennen.
- `seq = 0xFFFF` ist reserviert; ab `0xFFFE` muss die Sitzung neu aufgebaut werden (`SESSION`), bevor ein Nonce wiederkehren könnte.
- Hook `on_seq_accepted(ctx, seq)`: erlaubt, die höchste akzeptierte `seq` dauerhaft zu speichern (Schutz gegen Replay nach Neustart).
- Offener Punkt: die Schlüsselvereinbarung (z. B. ephemerer X25519 + HKDF auf Basis des BLE-Bondings) ist in v1 noch nicht festgelegt; sie liefert Schlüssel und `salt`.

## 6. History (Ereignisprotokoll)

- Ringpuffer (128 Einträge) mit **persistenten, streng steigenden 32-Bit-IDs** ab 1. Beim Booten übergibt die Plattform die gespeicherte nächste ID (`op_log_restore`), damit IDs Neustarts überleben; die Events selbst liegen im RAM (Flash-Persistenz ist Plattformaufgabe, offener Punkt).
- `GetHistory(FROM_ID)` liefert ab `max(FROM_ID, OLDEST_EVENT_ID)` bis zu 10 Events (passt in ein Frame inkl. 8-Byte-Tag). Paging: nächstes `FROM_ID` = letzte ID + 1; fertig, wenn `FROM_ID ≥ NEXT_EVENT_ID`. Eine Lücke (`FROM_ID < OLDEST`) zeigt überschriebene Events an.
- Event-Typen (`type`, Felder `a`/`b`): 1 BOOT, 2 BOLUS_START (a = mU), 3 BOLUS_DONE, 4 BOLUS_CANCEL (a = nicht geförderte mU), 5 TEMP_START (a = mU/h, b = min), 6 TEMP_DONE, 7 TEMP_CANCEL, 8 TEMP_COMM_FALLBACK, 9 BASAL_SET (a = Segmente), 10 SUSPEND, 11 RESUME, 12 FILL (a = mU), 13 PRIME (a = Schritte), 14 FAULT (a = neue Bits), 15 ACK (a = Maske), 16 LOW_RESERVOIR (a = mU), 17 LOW_BATTERY (a = mV).
- `time_s` = Sekunden seit Boot (der Pod hat keine Wanduhr; das Phone ordnet über BOOT-Events zu).

## 7. Beispiele (Hex)

GetStatus, `seq = 1` (Klartext):

```
01 01 00 01 00 00 00 BB 7A
```

Bolus 2,00 IE (`AMOUNT_MU = 2000`), `seq = 0x0102`:

```
01 05 00 02 01 06 00 05 04 D0 07 00 00 38 31
```

Antwort `OK` auf diesen Bolus:

```
01 85 02 02 01 03 00 01 01 00 34 06
```

## 8. Versionierung

- `version` im Frame ist die Hauptversion; inkompatible Änderungen erhöhen sie (`VERSION`-Fehler bei Abweichung).
- Kompatible Erweiterungen = neue Tags / neue optionale Felder (alte Empfänger überspringen sie). Neue Befehls-IDs sind ab 0x0C vergeben.
- `FW_VERSION` im Status erlaubt dem Phone, Funktionen zu erkennen.

## 9. Offene Punkte

1. Schlüsselvereinbarung und Pairing-Ablauf (Abschnitt 5.2).
2. Echte AES-CCM-Anbindung (CRACEN/PSA) und Persistenz von `seq`, Event-IDs und Reservoirstand in Flash.
3. Alarm-Characteristic (ungefragte Alarme) für v1.x.
4. Motorstrom/Back-EMF als zusätzlicher Okklusions-Eingang (heute nur Encoder).
5. Grenzwerte `BATTERY_CRITICAL`/`LOW` sind Annahmen, mit der realen Akku-Entladekurve abgleichen.
