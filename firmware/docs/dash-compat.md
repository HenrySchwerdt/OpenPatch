# DASH-Kompatibilitätsmodus – Portierungsplan

> Status: **Plan, kein Code.** Es wurde bewusst **kein** ESP-Sim-Code kopiert (Lizenzentscheidung offen, Abschnitt 6).
> Experimentelles DIY-Gerät, kein Medizinprodukt. „Omnipod“ und „DASH“ sind Marken von Insulet; der Modus ist
> Interoperabilität zu Entwicklungszwecken und wird nicht als Omnipod beworben.

Ziel (spec/design-parameters.md, Abschnitt 6.2): Der OpenPatch-Pod meldet sich im BLE wie ein Omnipod-DASH-Pod, sodass
Trio über das vorhandene `OmnipodKit` (loopandlearn) mit ihm spricht – ohne eigenes `OpenPatchKit` auf dem Phone.
Omnipod 5 wird **nicht** emuliert (P-256/ECDSA-Transkripte, Key-Manager).

## 1. Referenz: nightscout/ESP-Sim

Gelesen per `gh api` am 2026-11-18, Stand `be757a0` (2026-11-15). Beschreibung: „Simulator for Pumps and CGM simulators for
ESP32 Boards“, Sprache C, ESP32-S3, **GPL-3.0** (alle geprüften Quelldateien tragen `SPDX-License-Identifier: GPL-3.0-or-later`;
`x25519.c` basiert auf dem gemeinfreien TweetNaCl). Der Pod-Teil ist ein C-Port des Go-Simulators `jeremybarnum/pod`
(selbst aus `LoopKit/pod` und `0pen-dash`). **Es ist Testequipment: es fördert nichts und ist nicht für Therapie gedacht** –
für uns ist es deshalb nur die Protokollreferenz, nicht die Abgabelogik.

### 1.1 Repository-Struktur (relevant)

| Pfad | Inhalt |
|---|---|
| `components/dashpod/include/dash.h` | öffentliche API: `dash_msg_t`, `dash_state_t`, `dash_io_t`, `dash_pod_init/run`, Antwort-Builder (`dash_rsp_*`), Advertising-Helfer |
| `components/dashpod/include/dash_internal.h` | interne Primitive: `dash_crc16/32`, `dash_cmac`, `dash_ccm_encrypt/decrypt`, `dash_x25519`, `dash_milenage`, Plattform-Hooks `dash_aes128_encrypt_block`, `dash_sha256`, `dash_random`, P-256 (nur O5) |
| `src/link.c` | Link-Layer: RTS/CTS auf der Command-Characteristic, 20-Byte-Fragmente auf der Data-Characteristic, CRC-32, Success/Fail |
| `src/message.c` | „TW“-Nachrichten (`CTwiPacket`): Header 16 Byte, Typen CLEAR/ENCRYPTED/SESSION/PAIRING, Marshal/Unmarshal, Nonce |
| `src/pair.c` | Pairing: X25519-Schlüsselaustausch + CMAC-Bestätigungen → LTK (Felder `SP1=`,`SP2=`,`SPS1=`,`SPS2=`,`SP0GP0`) |
| `src/eap.c` | Sitzungsaufbau EAP-AKA mit Milenage → Sitzungsschlüssel `ck` und `nonce_prefix` |
| `src/crypto.c` | CRC-32, CRC-16 (OmnipodKit-Tabelle), AES-CMAC, AES-CCM, Milenage – alles auf einer AES-128-Blockfunktion aufgebaut |
| `src/x25519.c` | X25519 (TweetNaCl-Stil) |
| `src/command.c` | Parser für entschlüsselte Befehle `S0.0=<len><cmd>,G0.0` |
| `src/response.c` | Antwortkörper (`general`, `detailed`, Typ 1/3/5/46/50/51, NACK, Version, SetUniqueId) |
| `src/pod.c` | Zustandsmaschine des Pods, Advertising-Inhalte, Befehlsausführung |
| `src/platform_mbedtls.c`, `src/o5.c` | ESP-Plattformbindung bzw. Omnipod-5-Pairing – für uns **nicht** zu übernehmen (O5 entfällt, Krypto über PSA) |
| `test/host/golden_dash.h` | Golden Vectors (Pairing, EAP, LTK, CK, Nonce, verschlüsselte `GetVersion`-Nachricht), erzeugt von `tools/golden/gen.sh` aus dem Go-Original |
| `test/host/host_io.c` | Host-Implementierung von `dash_io_t` (Tests laufen auf macOS) |

### 1.2 Plattform-Abstraktion `dash_io_t`

Der Kern ist laut `dash.h` portables C ohne ESP-IDF-Abhängigkeit; die Plattform liefert genau diese Struktur (plus eine AES-128-Blockfunktion):

```c
typedef struct {
    void *ctx;
    bool    (*next_event)(void *ctx, dash_ev_t *ev, uint32_t timeout_ms); /* CMD/DATA-Write, CONNECTED, DISCONNECTED, STOP */
    void    (*notify_cmd)(void *ctx, const uint8_t *p, size_t n);
    void    (*notify_data)(void *ctx, const uint8_t *p, size_t n);
    void    (*disconnect)(void *ctx);
    void    (*advertise)(void *ctx, const dash_adv_t *adv);
    int64_t (*now_ms)(void *ctx);            /* Wanduhr, ms seit Unix-Epoche */
    void    (*save)(void *ctx, const dash_state_t *st);
    void    (*lock)(void *ctx);  void (*unlock)(void *ctx);
    void    (*crash)(void *ctx);
} dash_io_t;
```

`dash_pod_run()` ist eine blockierende Endlosschleife über `next_event`; `dash_state_t` (Pairing-LTK, Pod-ID, `msg_seq`, `cmd_seq`,
`nonce_seq`, Session-Schlüssel, `progress`, Reservoir in Pulsen à 0,05 IE, Alarme, Fehler …) wird über `save()` persistiert.

## 2. Protokollüberblick (aus ESP-Sim abgeleitet)

**Advertising.** Der Pod sendet **9 UUIDs (16 Bit)** als vollständige Liste: `0x4024`, dann `0xC001` (Alarm aktiv: `0xC005`, Fehler: `0xC00A`;
unpaired: `0x2470`), `0x000A`, **Pod-ID-Hälften** (Bytes 0–1 und 2–3 der 4-Byte-ID; unpaired `0xFFFF`/`0xFFFE`), `0x0814`, `0x6DB1`, `0x0006`, `0xE451`.
Dazu Herstellerdaten im iBeacon-Format (25 Byte, beginnend `4C 00 02 15`, mit Fehler-/Alarm-Bytes) und der Gerätename (ESP-Sim: `" :: Fake POD ::"`).
Der ESP-Sim nutzt erweiterte Advertising-Sätze (Zephyr: `bt_le_ext_adv_*`, nRF54L15 unterstützt das); Aufteilung Advertising/Scan-Response
ist aus `main/ble.c` zu übernehmen.

**GATT.** Service `1A7E4024-E3ED-4464-8B7E-751E03D0DC5F`; Characteristics `…2441` (Command) und `…2442` (Data); `…2443` ist nur Omnipod 5.
Alle Characteristics: Write, Write-Without-Response, Notify; **keine** Link-Layer-Verschlüsselung/Bonding nötig (Sicherheit liegt in der Anwendungsschicht).
(ESP-Sim bildet die 128-Bit-UUIDs mit einem Makro `DASH_UUID(b12,b13)`; Basis `…E3ED-4464-8B7E-751E03D0DC5F`.)

**Link-Layer** (`link.c`): Nachricht anbieten mit **RTS** (Command-Characteristic) → Phone antwortet **CTS** → Fragmente à 20 Byte auf Data mit **CRC-32**
→ **Success/Fail**. Quirks des Go-Originals sind beibehalten (kurze Nachrichten: erstes Paket bis 21 Byte; nur mehrfragmentige Nachrichten warten auf Success).
ATT-MTU 23 genügt – im DASH-Modus keine MTU-Verhandlung erzwingen.

**Nachrichtenschicht** (`message.c`): 16-Byte-Header (Version, EQOS, Flags, Typ, `seq`, `ack_num`, `src`/`dst` je 4 Byte), Nutzlast; verschlüsselte Nachrichten tragen
Chiffretext + **8-Byte-CCM-Tag**; der Header ist AAD. Befehle stehen entschlüsselt als `S0.0=<len><cmd>…,G0.0` (+CRC-16 mit OmnipodKit-Tabelle).

**Pairing** (`pair.c`): **X25519**-Schlüsseltausch, Bestätigungen per **AES-CMAC** → **LTK** (16 Byte).
**Achtung:** ESP-Sim setzt privaten Pod-Schlüssel und Nonce auf **0** („a simulator needs no secrecy“). Für ein echtes Gerät **inakzeptabel** – dort `dash_random()` (CRACEN-TRNG) verwenden.

**Sitzung** (`eap.c`): **EAP-AKA mit Milenage** (RAND/RES/AUTN, SQN-Zähler `eap_aka_seq`) → `ck` (16 Byte) und `nonce_prefix` (8 Byte); danach **AES-128-CCM**
mit Nonce = `prefix ‖ Zähler` (`dash_nonce(prefix, seq, pod_receiving)`), Zähler `nonce_seq` persistent.

## 3. Portierungsplan nRF54L15 / Zephyr

### 3.1 Architektur

- Neues Verzeichnis `firmware/dash/` (GPL-Komponente, siehe Abschnitt 6) mit **unverändert übernommenem** `components/dashpod/{include,src}` (außer `o5.c`, `platform_mbedtls.c`) – möglichst als Git-Subtree, damit Upstream-Fixes einfließen.
- `firmware/dash/dash_io_zephyr.c` implementiert `dash_io_t`; `firmware/dash/dash_bridge.c` übersetzt DASH-Befehle in Aufrufe des vorhandenen Kerns (`op_pump_*`, Abschnitt 4).
- Moduswahl **zur Build-Zeit** (`CONFIG_OPENPATCH_MODE_DASH`) mit eigener `prj-dash.conf`: native Firmware und DASH-Firmware sind getrennte Images (vermeidet GATT-/Advertising-Mischbetrieb und trennt die Lizenzfrage sauber). Laufzeit-Umschalten kann später per Taste beim Einschalten folgen.
- `dash_pod_run()` läuft in einem eigenen Zephyr-Thread (Stack ≈ 6 KB, Priorität unter dem BT-Stack). Der **Delivery-Tick** (`op_pump_tick`) bleibt im Haupt-Thread; Zugriff auf den Kern über einen Mutex oder (besser) eine Message-Queue vom DASH-Thread zum Haupt-Thread, damit der Kern single-threaded bleibt.

### 3.2 `dash_io_t` auf Zephyr

| Feld | Zephyr-Umsetzung |
|---|---|
| `next_event` | `k_msgq`/`k_poll`: GATT-Write-Callbacks (Command/Data) und `bt_conn_cb.connected/disconnected` stellen `dash_ev_t` ein; Timeout → `K_MSEC` |
| `notify_cmd` / `notify_data` | `bt_gatt_notify_uuid()` auf den zwei Characteristics (20-Byte-Pakete, Default-MTU) |
| `disconnect` | `bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN)` |
| `advertise` | `bt_le_ext_adv_set_data()` mit 9×UUID16 + Herstellerdaten + Name (Inhalte aus `dash_advertised_services`/`dash_manufacturer_data`); bei Änderung von Pod-ID/Alarm/Fehler neu setzen |
| `now_ms` | Wanduhr = gespeicherter Epoche-Offset + `k_uptime_get()`. nRF54L15 hat keine batteriegepufferte RTC im Pod → Offset wird gespeichert und bei Pairing/Befehlen vom Phone nachgeführt (**offen:** welcher DASH-Befehl die Controller-Zeit transportiert – aus OmnipodKit klären) |
| `save` | Zephyr Settings/ZMS auf RRAM; `dash_state_t` ≈ 200 Byte, Schreiben nur bei Änderung, wear-aware (Zähler wie `nonce_seq` nicht bei jedem Paket in Flash) |
| `lock`/`unlock` | `k_mutex` (nur nötig, falls ein zweiter Thread auf `dash_pod_t` zugreift) |
| `crash` | `sys_reboot()` (Testfunktion „crash next command“, im Release entfernen) |

### 3.3 Kryptographie

Der ESP-Sim-Kern verlangt nur `dash_aes128_encrypt_block`, `dash_sha256`, `dash_random` (+ P-256 nur für O5). Auf dem nRF54L15 über **PSA Crypto / CRACEN**:

- `dash_aes128_encrypt_block` → `psa_cipher_encrypt` mit `PSA_ALG_ECB_NO_PADDING` (ein Block) oder direkt CRACEN-AES.
- `dash_sha256` → `psa_hash_compute`; `dash_random` → `psa_generate_random` (CRACEN-TRNG).
- CMAC, CCM, Milenage und X25519 sind in ESP-Sim portables C auf der Blockfunktion – funktionieren unverändert; optional später auf `PSA_ALG_CMAC`/`PSA_ALG_CCM`/Curve25519-ECDH (CRACEN-beschleunigt) umstellen. Die Golden Vectors sichern jeden Austausch ab.
- **Privaten Pod-Schlüssel und Nonce im Pairing zufällig erzeugen** (siehe oben) und `ltk`, `ck` in geschütztem Speicher (KMU/PSA persistent keys) ablegen.
- O5-Code (`o5.c`, P-256, Zertifikat) entfällt → kleinerer Footprint.

### 3.4 Speicher, Puffer

`DASH_MSG_MAX` ist 2048 (nur wegen O5-Zertifikaten ≈ 1,1 KB); für DASH reichen ≈ 256 Byte → `dash_pod_t` (derzeit je 2 KB `rx_buf`/`tx_buf`) und `dash_msg_t` (liegt auf dem Stack) schrumpfen deutlich. Die nRF54L15 hat zwar 256 KB RAM, der Thread-Stack sollte trotzdem geprüft werden.

### 3.5 BLE-Besonderheiten

- **Kein SMP/Bonding** im DASH-Modus (`CONFIG_BT_SMP=n`, Characteristic-Permissions ohne Verschlüsselung) – anders als der native Modus.
- Verbindungsparameter und Advertising-Intervall so wählen, dass `OmnipodKit` (CoreBluetooth) zuverlässig findet/verbindet; mit realem Trio testen. Das Verhalten bei Reconnect (`DASH_EV_CONNECTED` bricht laufende Link-Übertragung ab) übernehmen.
- Gerätename: nicht „Omnipod“ imitieren, sondern eine eigene Kennung wählen, sofern OmnipodKit nicht nach dem Namen filtert (aus OmnipodKit prüfen; Scan erfolgt über die Service-UUIDs).

## 4. Abbildung DASH-Befehle → `delivery_engine`/Pump-Controller

ESP-Sim dekodiert absichtlich nur Kopf-Felder (`PROGRAM_INSULIN`: `table_num`, `duration`, `pulses`) und **liefert nichts**. Für den echten Pod müssen die vollständigen Programme dekodiert werden – das Format ist aus **OmnipodKit** (Programmierung von Basal-/Temp-/Bolus-Tabellen) abzuleiten; Golden Vectors aus OmnipodKit erzeugen (analog `tools/o5golden`).

Einheiten: 1 DASH-Puls = **0,05 IE = 50 mU** (passt zu unserem `OP_RATE_GRANULARITY_MU`/`OP_BOLUS_GRANULARITY_MU`). Bolusdauer in ESP-Sim: **2 s/Puls im Betrieb** = 1,5 IE/min = unsere Bolusrate; 1 s/Puls nur in der Aktivierung.

| DASH-Befehl (Code) | Wirkung auf unseren Pod |
|---|---|
| `SET_UNIQUE_ID` (0x03) | Pod-ID (4 Byte) speichern → fließt in Advertising-UUIDs; kein Eingriff in die Engine |
| `GET_VERSION` (0x07), `CNFG_DELIV_FLAG` (0x08) | feste Antworten (`dash_rsp_version`); Firmware-/Hardwarekennung bewusst als „Fremdgerät“ wählen, falls OmnipodKit es zulässt |
| `GET_STATUS` (0x0E), Status-Typen 0/1/2/3/5/0x46/0x50/0x51 | aus `op_status_t` aufbauen: Reservoir in Pulsen (`reservoir_mu / 50`), Bolus aktiv/Rest, Temp aktiv, `progress` (8 ≥ 50 IE, 9 < 50 IE, 13 Fehler, 15 inaktiv), geförderte Pulsmenge, aktive Minuten, Fehler-/Alarmbytes |
| `PROGRAM_INSULIN` Tabelle 0 (Basal; im ESP-Sim-Log `PROGRAM_BASAL` 0x13) | 48 Halbstunden-Slots → `op_basal_schedule_t` (gleiche Nachbarslots zu Segmenten verschmelzen) → `op_pump_set_schedule()` |
| `PROGRAM_INSULIN` Tabelle 1 (Temp; Log `PROGRAM_TEMP_BASAL` 0x16) | Rate + `duration` (Halbstunden) → `op_pump_set_temp_basal(rate_mu_h, 30·duration)` |
| `PROGRAM_INSULIN` Tabelle 2 (Bolus; Log `PROGRAM_BOLUS` 0x17) | `pulses·50` mU → `op_pump_bolus()` |
| `STOP_DELIVERY` (Flags Bolus/Temp/Basal) | `op_pump_cancel_bolus()` / `op_pump_cancel_temp_basal()` / `op_pump_suspend()` |
| `PROGRAM_ALERTS` (0x19), `SILENCE_ALERTS`, `PROGRAM_BEEPS` (0x1E) | Alarm-Slots (Reservoir niedrig, Ablauf …) in Summer-/Alarmlogik; Reservoir-Alarm gegen `op_res_*` |
| `DEACTIVATE` (0x1C) | Abgabe stoppen (`suspend`), `progress = INACTIVE`; für den wiederverwendbaren Pod: erneute Aktivierung = neues Pairing nach Fill |
| unbekannte Befehle | NACK wie ESP-Sim (`dash_rsp_nack`) |

Zustandsführung: DASH-`progress`, `last_prog_seq`, `cmd_seq`/`msg_seq`/`nonce_seq`, Pod-ID und LTK **persistent** (`dash_state_t`); Reservoir/Abgabezähler aus dem Kern (nicht doppelt führen – die Quelle der Wahrheit bleibt `reservoir_model`).

Wichtige Regeln:

1. **Der Sicherheitsüberwacher bleibt oberste Instanz.** Jeder DASH-Befehl läuft durch `op_sv_check_*`. Lehnt er ab (z. B. Bolus > 10 IE), muss ein DASH-konformer NACK/Fehler zurückgehen, den Trio versteht (Verhalten mit realem Trio testen; ggf. Max-Bolus in Trio gleich oder kleiner setzen).
2. **Aktivierungsphase.** DASH aktiviert mit Prime (≈ 2,6 IE als Bolus bei `progress < …`) und Kanüleneinsetzen (0,5 IE). Unser Pod hat weder Schlauch noch Einstechmechanik (Insight-Flex-Kanüle wird vom Nutzer gesetzt; Totvolumen der Nadel ≈ 0,5 IE max.). Diese Pseudo-Boli dürfen **nicht** real gefördert werden (Gefahr, in den Körper zu fördern): im Zustand `PRIMING`/`INSERTING_CANNULA` nur quittieren (Timing wie das Original simulieren) bzw. höchstens `op_pump_prime()` (≤ 40 Schritte) ausführen. Reservoir-Abbuchung nur für real geförderte Schritte.
3. **Pod-Lebensdauer.** Trio erwartet 80 h; für die Anzeige wird die Aktivierungszeit bei jedem Pairing neu gesetzt (spec: „200-IE-Pod mit 80-h-Lebensdauer“). Nach Ablauf meldet DASH Alarme/`ACTIVATION_TIME_EXCEEDED` – für den wiederverwendbaren Pod bewusst nur anzeigen, nicht hart abschalten, bis das Konzept entschieden ist.
4. **Kommunikationsverlust.** Jede authentifizierte DASH-Nachricht ruft `op_de_comm_heartbeat()` auf; Temp-Basal fällt nach 30 min auf den Plan zurück (spec Abschnitt 7).
5. **Fehlerabbildung.** Unsere Fehlerbits (OCCLUSION, ENCODER_DEVIATION, RESERVOIR_EMPTY, BATTERY_CRITICAL, LIMIT_EXCEEDED, INTERNAL) müssen auf DASH-Fehlercodes (`fault`-Byte, Pod-Info-Typ 2/3/5) abgebildet werden, damit Trio den Alarm anzeigt statt „alles in Ordnung“ zu glauben. Tabelle aus OmnipodKit (`PodInfoFaultEvent`) ableiten – **offen**.
6. **Basalplan-Segmente.** DASH kennt 48 Halbstunden-Einträge; unser Kern erlaubt (Spec) 24 Segmente. Ein DASH-Plan mit mehr als 24 verschiedenen Nachbarsegmenten würde abgelehnt. Entscheidung nötig: `OP_BASAL_SEGMENTS_MAX` auf 48 anheben (Spec-Änderung) – empfohlen.

## 5. Teststrategie

1. **Golden Vectors übernehmen** (`test/host/golden_dash.h`, erzeugt aus dem Go-Original) und im Host-Test (`firmware/tests`) gegen die portierte Komponente laufen lassen: Pairing, EAP, LTK/CK, CCM, `GetVersion`.
2. `host_io.c`-Äquivalent (`dash_io_t` für den Host) wiederverwenden, um komplette DASH-Sitzungen gegen den Kern mit **Mock-HAL** zu fahren (Bolus/Temp/Basal-Programmierung → Schrittzahlen, Veto durch den Überwacher, Fehlerabbildung).
3. **Gegenprobe:** derselbe Trio-Testaufbau erst gegen ESP-Sim (ESP32-S3), dann gegen den OpenPatch-Pod; Abweichungen im Verhalten dokumentieren.
4. Prüfstand mit Wasser (kein Insulin, kein Körper): Bolus-/Basalgenauigkeit über die Waage, Okklusion/Encoder-Fehler provozieren, Alarmkette in Trio prüfen.

## 6. Lizenzfolgen (GPL-3.0)

ESP-Sim steht unter **GPL-3.0**; die gelesenen Quellen tragen `GPL-3.0-or-later`. Kopieren oder portieren von `components/dashpod` macht die Firmware zu einem **abgeleiteten Werk**:

- **Das gesamte DASH-Firmware-Image (inkl. Kern, HAL, Zephyr-Anwendung) muss unter GPL-3.0(-or-later) stehen**, sobald es ESP-Sim-Code enthält. Das entspricht bereits der Annahme in spec/design-parameters.md (Abschnitt 6.2).
- **Weitergabe** (Verkauf/Verschenken von Pods mit der Firmware, Binär-Downloads): Quellcode (auch der Kopplungs-/Bridge-Teile) muss mitgeliefert oder schriftlich angeboten werden; Lizenztexte und Urheberhinweise (ESP-Sim, `jeremybarnum/pod`, `LoopKit/pod`, `0pen-dash`, TweetNaCl) bleiben erhalten; Änderungen sind kenntlich zu machen.
- **GPLv3 §6 („Installation Information“)**: Für „User Products“ (typischerweise persönlich genutzte Geräte, hier voraussichtlich der Pod) müssen die Informationen bereitgestellt werden, um geänderte Firmware auf dem Gerät zu installieren. Ein **gesperrter Secure Boot** ohne Schlüsselweitergabe ist dann nicht zulässig. Das steht im Spannungsfeld zu Sicherheitsanforderungen (signierte Updates) – Lösung: Updates per Nutzerschlüssel/Open-Signing, offener Bootloader, dokumentierte Flash-Prozedur.
- **Trennung der Varianten:** Die native Firmware kann nur dann anders lizenziert (z. B. Apache-2.0/MIT) werden, wenn ihr Image **keinen** GPL-Code enthält. Ein gemeinsames Image mit DASH-Code ist GPL. Daher der Vorschlag getrennter Images (Abschnitt 3.1) – die Linkgrenze innerhalb eines Images trennt Lizenzen nicht.
- **Empfehlung:** gesamte Firmware unter **GPL-3.0-or-later** stellen (einfachste, konsistente Lösung, passt zur Zielgruppe der Open-Source-Closed-Loop-Community). `SPDX-License-Identifier` in alle Dateien in `firmware/` aufnehmen, sobald entschieden. Das ist keine Rechtsberatung – vor einer Weitergabe juristisch prüfen lassen (auch Marken- und Medizinprodukterecht).
- Protokollkenntnis aus OmnipodKit (loopandlearn) ist getrennt zu betrachten; deren Lizenz vor dem Übernehmen von Tabellen/Konstanten prüfen.

## 7. Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| 0 | Lizenzentscheidung; OmnipodKit analysieren (Programm-Payloads, Fehlercodes, Alarmslots, Zeitquelle) | Spezifikationsblatt, Golden Vectors für Programme |
| 1 | `components/dashpod` als Subtree nach `firmware/dash/`; Zephyr-CMake; `dash_io_zephyr.c`; Host-Test mit Golden Vectors | Pairing/Sitzung auf dem Host reproduzierbar |
| 2 | BLE-Bring-up auf nRF54L15 (Advertising, GATT, Link-Layer) mit iPhone/Trio | Trio findet den Pod und paart |
| 3 | `dash_bridge.c`: Befehle → Pump-Controller, Statusantworten, Fehlerabbildung | Trio programmiert Basal/Temp/Bolus am Prüfstand |
| 4 | Sicherheitsreview (Zufallsschlüssel, Persistenz von Zählern, Aktivierungsphase ohne Pseudo-Boli) | Review-Bericht |
| 5 | Prüfstand mit Wasser, Fehlerinjektion | Testprotokoll |

## 8. Offene Fragen / Risiken

1. Format der vollständigen `PROGRAM_INSULIN`-Payloads (Basal/Temp/Bolus) – ESP-Sim dekodiert nur den Kopf.
2. Fehlercode-Abbildung unserer Fehlerbits auf DASH-Faults.
3. Zeitquelle (Wanduhr) im Pod und welche DASH-Nachricht sie liefert.
4. Anzahl Basalsegmente 24 vs. 48 (Spec-Änderung).
5. Verhalten von Trio/OmnipodKit bei abgelehnten Befehlen (Limit-Veto) und bei abweichenden Versions-/Hardwarekennungen.
6. Lizenz und Marken (Abschnitt 6); Regulierung: ein DASH-emulierendes Fremdgerät steuert Insulin über Software, die dafür nicht freigegeben ist – ausdrücklich nur experimentell.
7. Persistenz-Verschleiß (RRAM-Zyklen) bei häufig geänderten Zählern.
