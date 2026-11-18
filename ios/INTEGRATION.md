# OpenPatchKit in Trio integrieren

> **Experimentell.** OpenPatch ist ein DIY-Prototyp und kein Medizinprodukt. Diese Anleitung ist für Entwickler gedacht, die
> Trio lokal selbst bauen. Nichts davon wurde gegen echte Hardware getestet.

Stand der Abhängigkeiten (geprüft am 2026-11-18):

| Komponente | Version |
|---|---|
| Trio `main` | LoopKit-Submodul `loopandlearn/LoopKit` @ `f974241f5f25053d51da3e80833c85b13c387e6f` (Branch `trio`) |
| OpenPatchKit | gegen genau diesen LoopKit-Stand gebaut und getestet (iOS-Simulator, Xcode 26.3) |
| Mindest-iOS | 17.0 (Trio-Kits wie MedtrumKit nutzen 17.5/17.6) |

Es gibt zwei Wege, den Pod an Trio anzubinden:

* **Variante A, nativ:** Trio bekommt den neuen Treiber `OpenPatchKit` (dieses Verzeichnis). Echte Werte für Reservoir, Akku,
  wiederverwendbarer Pod, 0,05-IE-Raster, Pod-Größen 70/100/200 IE.
* **Variante B, DASH-Kompatibilitätsmodus:** Der Pod emuliert Omnipod DASH. Trio bleibt **unverändert** und nutzt das vorhandene `OmnipodKit`.

---

## Variante A: OpenPatchKit nativ einbauen

### 0. Was in `ios/OpenPatchKit/` liegt

```
OpenPatchKit/                 (Verzeichnis ios/OpenPatchKit/)
├── OpenPatchKit.xcodeproj    generiert, 3 Frameworks + Tests
├── OpenPatchCore/            reines Swift-Package (kein LoopKit): Einheiten, Zustandsmaschine, Wire v1, Simulator
├── OpenPatchKit/             Framework: OpenPatchPumpManager, State, Transport (CoreBluetooth)
├── OpenPatchKitUI/           Framework: Einrichtung (Größe, Koppeln, Befüllen, Entlüften, Aufstecken), Einstellungen
├── OpenPatchKitTests/        XCTest gegen LoopKit + simulierten Pod
├── Support/                  Umbrella-Header, Config.xcconfig (Signing-Team)
└── scripts/                  generate_xcodeproj.rb, generate_strings.py
```

Das Xcode-Projekt ist erzeugt. Nach Änderungen an der Dateiliste neu erzeugen (benötigt die `xcodeproj`-Gem aus CocoaPods):

```bash
cd ios/OpenPatchKit
GEM_HOME=$(dirname $(dirname $(readlink -f $(which pod))))/libexec ruby scripts/generate_xcodeproj.rb
python3 scripts/generate_strings.py        # en/de Localizable.strings neu schreiben (bricht ab, wenn eine Übersetzung fehlt)
```

### 1. Als Submodul bzw. Verzeichnis in den Trio-Checkout holen

Trio erwartet jedes Kit als Verzeichnis auf oberster Ebene mit eigenem `.xcodeproj` (wie `MedtrumKit/MedtrumKit.xcodeproj`).

**Variante 1a, eigenes Git-Repository (sauber, wie die anderen Kits):**

```bash
# im ai-insulin-pump-Repo: ios/OpenPatchKit als eigene History abspalten
git subtree split --prefix=ios/OpenPatchKit -b openpatchkit
git push git@github.com:<dein-konto>/OpenPatchKit.git openpatchkit:main

# im Trio-Checkout
cd ~/dev/Trio
git submodule add https://github.com/<dein-konto>/OpenPatchKit.git OpenPatchKit
git submodule update --init --recursive
```

**Variante 1b, rein lokal zum Ausprobieren (ohne Remote):**

```bash
cd ~/dev/Trio
ln -s ~/dev/ai-insulin-pump/ios/OpenPatchKit OpenPatchKit      # oder: cp -R ...
```

Beim Symlink bitte darauf achten, `OpenPatchKit` nicht versehentlich in Trio zu committen.

Optional, wenn du den Fork pflegen willst (analog zu `MedtrumKit`):

* `.gitmodules`: Eintrag `[submodule "OpenPatchKit"] path = OpenPatchKit  url = https://github.com/<dein-konto>/OpenPatchKit.git`
* `scripts/define_common_trio.sh`: Zeile `<dein-konto>:OpenPatchKit:main \` in die Submodul-Liste
* `scripts/swiftformat.sh`: `--exclude OpenPatchKit \`
* `.github/CODEOWNERS`: Zeile `OpenPatchKit  @nightscout/trio-pump-codeowners`

### 2. Workspace-Eintrag

In `Trio.xcworkspace/contents.xcworkspacedata` neben `MedtrumKit` ergänzen:

```xml
   <FileRef
      location = "group:OpenPatchKit/OpenPatchKit.xcodeproj">
   </FileRef>
```

Danach `Trio.xcworkspace` öffnen. Es müssen die Schemes `OpenPatchKit` und die Targets `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI` sichtbar sein.
Das OpenPatch-Projekt löst `LoopKit.framework` und `LoopKitUI.framework` über `BUILT_PRODUCTS_DIR` auf (wie MedtrumKit). Es lässt sich daher **nur im Workspace**
bauen, nicht allein.

### 3. Frameworks in das Trio-App-Target einbinden

Wie bei `MedtrumKit.framework` (siehe `Trio.xcodeproj`, Phase "Embed Frameworks", `CodeSignOnCopy, RemoveHeadersOnCopy`):

1. Target **Trio** → *General* → *Frameworks, Libraries, and Embedded Content* → `+` →
   `OpenPatchCore.framework`, `OpenPatchKit.framework`, `OpenPatchKitUI.framework` (Quelle: *Workspace*, Projekt OpenPatchKit).
2. Alle drei auf **Embed & Sign** stellen.
3. Reihenfolge ist egal, `OpenPatchKitUI` hängt von `OpenPatchKit` und `OpenPatchCore` ab (im Projekt als Target-Dependencies hinterlegt).

`Info.plist` der App: Trio hat Bluetooth bereits (`NSBluetoothAlwaysUsageDescription`, `UIBackgroundModes` mit `bluetooth-central`). Nichts ergänzen,
aber prüfen. Ohne `bluetooth-central` bekommt die App keine Hintergrund-Verbindung zum Pod.

### 4. `DeviceCatalog.swift`: Pumpe eintragen

Datei: `Trio/Sources/APS/Devices/DeviceCatalog.swift` (laut Datei: "Adding a device means adding one entry to this file").

**4.1 Imports** (alphabetisch bei den anderen `import`-Zeilen):

```swift
import OpenPatchKit
import OpenPatchKitUI
```

`OpenPatchKitUI` wird nur wegen der `PumpManagerUI`-Konformität benötigt (wie `MockKitUI`). Sie wird per Extension in `OpenPatchKitUI` deklariert.

**4.2 Hersteller-Abschnitt.** `OpenPatchPumpManager` hat keinen Eintrag in `DeviceManufacturer`. Entweder bestehenden Abschnitt `.otherSources` nutzen
oder einen eigenen anlegen:

```swift
enum DeviceManufacturer: CaseIterable {
    // ...
    case openPatch            // NEU
    // ...
    var displayName: String {
        switch self {
        // ...
        case .openPatch: return "OpenPatch"      // Markenname, bewusst nicht lokalisiert
        }
    }
    // sortRank: 'default' liefert 0, passt
}
```

**4.3 Eintrag in `DeviceCatalog.pumps`** (vor dem `MockPumpManager`-Eintrag):

```swift
PumpCatalogEntry(
    OpenPatchPumpManager.self,
    manufacturer: .openPatch,
    name: "OpenPatch (experimentell)",
    supportedModels: ["OP-70", "OP-100", "OP-200"],
    icon: .none,                                   // kein Asset; Fallback-Symbol "ivfluid.bag"
    basalCapability: BasalRateCapability(supportedRates: OpenPatchPumpManager.onboardingSupportedBasalRates),
    reportsRewindEvents: false                     // Patch-Pumpe, nichts zurückzuspulen
),
```

* `id` ist `OpenPatchPumpManager.pluginIdentifier` = `"OpenPatch"`. Unter diesem Namen wird der Pumpenzustand persistiert. Nicht mehr ändern.
* `OpenPatchPumpManager.onboardingSupportedBasalRates` ist ein gleichmäßiges Raster 0,05…30 IE/h (Trio prüft Einheitlichkeit in `DeviceCatalogTests`).
* `allowedInsulinTypes` bleibt Standard (`DeviceCatalog.defaultAllowedInsulinTypes`).

**4.4 Tests.** `TrioTests/DeviceCatalogTests.swift` prüft Katalogeinträge (u. a. Icons und Basalraster). Dort den neuen Eintrag mit abdecken.

### 5. Optional: Alarm-Katalog

`Trio/Sources/Services/Alerts/AlertCatalogRegistry.swift` legt pro Pumpe die Alarmstufe fest. **Ohne Eintrag funktioniert OpenPatch trotzdem**:
`TrioAlertManager` reicht Alarme ohne Katalogeintrag unverändert durch (`podFault` wird vom Treiber als `.critical` ausgelöst, die übrigen als `.timeSensitive`).
Wer die Alarmstufen in Trios "Device Alarms" konfigurierbar haben will, ergänzt:

```swift
// in entries: ... + medtrumEntries + openPatchEntries + ...
private extension AlertCatalogRegistry {
    static let openPatchEntries: [Alert.CatalogEntry] = [
        addEntry("OpenPatch", "lowReservoir", .timeSensitive, "Low Insulin", "Reservoir", .reservoirLow),
        addEntry("OpenPatch", "podFault", .critical, "Pod Fault", "Delivery", .hardwareFault),
        addEntry("OpenPatch", "batteryLow", .timeSensitive, "Pod Battery Low", "Battery", .pumpBatteryLow),
        addEntry("OpenPatch", "tempBasalCommLoss", .timeSensitive, "Connection Lost", "Connectivity", .pairingFailed)
    ]
}
```

(`addEntry(manager, alertID, level, title, category, concept)`; Konzepte aus `AlertCatalogVendor.swift`. `tempBasalCommLoss` hat dort kein passendes Konzept,
`.unspecified` ist ebenfalls möglich.)

### 6. Bauen und Signieren

* **Team:** `OpenPatchKit/Support/Config.xcconfig` übernimmt `DEVELOPER_TEAM` aus Trios `ConfigOverride.xcconfig` (zwei bzw. drei Ebenen darüber, `#include?`).
  Das ist dieselbe Datei, die laut Trio-README das Team setzt (`echo 'DEVELOPER_TEAM = XXXXXXXXXX' > ConfigOverride.xcconfig`).
  Fehlt sie, in Xcode für die Targets `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI` unter *Signing & Capabilities* das Team wählen (Automatic Signing).
* **Bundle-IDs** der Frameworks: `org.openpatch.OpenPatchCore|OpenPatchKit|OpenPatchKitUI`. Frameworks brauchen keine eigene App-ID-Registrierung;
  mit kostenlosem Apple-Account funktioniert das Embedden. Wer eine andere Kennung will, ändert `PRODUCT_BUNDLE_IDENTIFIER` in `scripts/generate_xcodeproj.rb`.
* **Keine Entitlements** in den Frameworks nötig. Bluetooth-Berechtigung und Hintergrundmodus gehören zur App (siehe Schritt 3).
* **Simulator:** Der iOS-Simulator hat kein Bluetooth. In Debug-Builds (`allowDebugFeatures`) bietet der Kopplungsbildschirm
  "Simulierten Pod verwenden (Entwicklung)" an; dann läuft ein In-Memory-Pod in Echtzeit (`OpenPatchSimulator`).
* **Build-Reihenfolge:** Beim ersten Bauen zuerst `LoopKit`, dann `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI`, dann `Trio` (Xcode ordnet das über die Target-Dependencies selbst).

### 7. Prüfen

```bash
# reines Swift, ohne Xcode-Projekt, läuft auf macOS
cd ios/OpenPatchKit/OpenPatchCore && swift test

# Treiber gegen echtes LoopKit, auf dem Simulator (Workspace mit LoopKit + OpenPatchKit nötig)
xcodebuild test -workspace Trio.xcworkspace -scheme OpenPatchKit \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' CODE_SIGNING_ALLOWED=NO
```

Danach in Trio: *Einstellungen → Pumpe → OpenPatch*. Ablauf der Einrichtung: Pod-Größe → Koppeln → Befüllen (Spritze, Menge bestätigen) →
Entlüften → Aufstecken auf den Kanülenkopf → Start. Für spätere Pod-Wechsel: Einstellungen → "Pod vom Körper abnehmen" → "Pod neu befüllen und weiterverwenden".

### 8. Bekannte Lücken (ehrlich)

* **Nie gegen Hardware gelaufen.** `CoreBluetoothLink` kompiliert, wurde aber nur gegen das Protokoll-Dokument und einen Fake-Firmware-Stub getestet.
* **Sicherheitsschicht fehlt:** Die Spec sieht AES-CCM und Replay-Schutz vor (Abschnitt 5), die Schlüsselvereinbarung ist dort noch offen.
  Der Treiber sendet Klartext-Frames (Firmware mit `allow_plaintext` nötig). Die Befehls-`seq` wird in `rawState` persistiert (`commandSequence`) und nach einem
  Neustart mit 16 Schritten Sicherheitsabstand fortgesetzt (der Host speichert asynchron, der Pod toleriert Lücken). Die Spec liefert im Status keine
  "zuletzt akzeptierte seq", daher gibt es keine Rück-Synchronisation vom Pod; nach einem Pod-Reboot mit zurückgesetztem Zähler würde der Pod Frames still verwerfen.
* **Kein Push von Alarmen:** v1 hat keine Alert-Characteristic. Alarme und Boli-Ende kommen per `GetHistory`-Polling nach jedem Statuslesen.
  Der Verlaufs-Cursor wird in `rawState` persistiert (`historyCursor`); Ereignisse unterhalb des Cursors werden nie erneut ausgeliefert (Deduplizierung über die
  Ereignis-ID), verpasste kommen nach dem Neustart genau einmal. Zustellung ist at-least-once: stürzt die App zwischen Auslieferung und Speichern ab, kann ein Alarm doppelt kommen.
* **Bolus-ID:** Der Pod vergibt keine Bolus-ID; sie wird in `V1Transport` gemerkt. Nach App-Neustart während eines Bolus wird dieser als fremder Bolus übernommen.
* **Pod meldet keine Lebenszyklusphase:** `paired/filled/primed/…` führt die App (`phaseHint`), der Pod kennt nur `suspended`, `filled` und Fehlerbits.
* **HUD/Lebensdauer:** keine Kachel für Loop-HUD (Trio nutzt sie nicht), kein Ablauf-Fortschritt (wiederverwendbarer Pod).
* **Temp-Basal-Dauer** wird auf der Leitung auf Vielfache von 30 min aufgerundet (Spec 3.1); Loop sendet ohnehin 30-min-Vielfache.
* **Alarmstufen** und Texte sind Platzhalter, `Prime`-Menge (0,5 IE) und Füllgrenzen (min. 10 IE) müssen nach dem ersten Wassertest angepasst werden
  (`PumpConstants`, `PodSize`).

---

## Variante B: DASH-Kompatibilitätsmodus (keine Trio-Änderung)

Der Pod emuliert das Omnipod-DASH-BLE-Protokoll (Referenz: `nightscout/ESP-Sim`, **GPL-3.0**, daher ist der Firmware-Teil dann ebenfalls GPL-3.0).
Trio sieht einen normalen DASH-Pod und spricht ihn über das bereits eingebundene `OmnipodKit` (`OmniPumpManager`, Katalogeintrag "Omnipod" mit den Modellen
"Classic, DASH, 5").

**Was du in Trio tust:** gar nichts am Code. Kein Submodul, kein Workspace-Eintrag, kein `DeviceCatalog`-Eintrag.

1. Pod-Firmware im DASH-Modus flashen (Firmware-Team).
2. Trio → *Einstellungen → Pumpe → Omnipod* (Modell DASH) → neuen Pod koppeln. Der Pod meldet sich per BLE wie ein DASH-Pod.
3. Den normalen Omnipod-Ablauf durchlaufen (Befüllen, Entlüften, Kanüle setzen, Start). Die App verhält sich wie bei einem DASH-Pod.

**Was `OmnipodKit` von einem DASH-Pod erwartet** (aus `OmnipodKit/OmnipodCommon/Pod.swift`, Branch `dev`) und was der OpenPatch-Pod daher vortäuschen muss:

| DASH-Wert in `OmnipodKit` | Wert | Folge für OpenPatch |
|---|---|---|
| Pulsgröße / Bolusgeschwindigkeit | 0,05 IE, 2 s je Puls = 1,5 IE/min | passt exakt zu OpenPatch (0,05 IE, 1,5 IE/min) |
| Reservoirkapazität | 200 IE | Trio sieht immer 200 IE, auch bei OP-70/OP-100 |
| Reservoir-Anzeige | exakte Werte nur unter 50 IE, darüber "50+" (Magic Number 51,15) | DASH-Pod meldet oberhalb 50 IE keinen genauen Stand; der native Modus zeigt echte Werte |
| Prime | 2,6 IE mit 1 s je Puls | der OpenPatch-Pod hat keinen Schlauch zu füllen, sondern nur eine 30G-Nadel: Firmware muss Prime-Kommando akzeptieren, aber nur das echte Totvolumen fördern (< 0,6 IE), und die Reservoir-Buchhaltung entsprechend führen |
| Kanüle setzen | 0,5 IE | Kanüle liegt schon (Insight Flex): Kommando quittieren, nichts fördern |
| Lebensdauer | 80 h (`serviceDuration`), Erinnerung 7 h vorher | Trio zeigt Pod-Ablauf nach 80 h und verlangt Pod-Wechsel: bei jedem Wechsel Pod "neu koppeln", im Pod-Zustand zurücksetzen und neu befüllen |
| Basalprofil | max. 24 Einträge, 30-min-Raster | Pod muss 24 Segmente akzeptieren |
| Temp-Basal | Vielfache von 30 min, bis 12 h; max. 30 IE/h; max. Bolus 30 IE | die Pod-Grenzen (10 IE Bolus, 5 IE/h Basal, 15 IE/h gesamt, siehe `spec/design-parameters.md` §7) sind **strenger**; Firmware antwortet dann mit einem Fehler, den `OmnipodKit` als abgelehnte Abgabe anzeigt. Die Grenzen daher in Trios Einstellungen (Max Bolus, Max Basal) gleich oder niedriger setzen |
| Kommunikationsverlust | DASH-Semantik: Temp-Basal läuft max. 30 min weiter | identisch zur OpenPatch-Spec (§7) |

**Nicht unterstützt:** Omnipod 5 (P-256/ECDSA-signierte Transkripte, Key-Manager mit App Attest), siehe `spec/design-parameters.md` §6.

**Wann welche Variante?** DASH-Modus ist der schnellste Weg zu einem Test ohne Trio-Änderung, kostet aber Reservoir-Genauigkeit, Pod-Größenwahl und die
wiederverwendbare Lebensdauer. Der native Modus (Variante A) liefert echte Werte, braucht aber die Änderungen in diesem Dokument und trägt das Risiko eines
selbst gepflegten Trio-Forks.
