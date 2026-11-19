# Integrating OpenPatchKit into Trio

> **Experimental.** OpenPatch is a DIY prototype and not a medical device. This guide is intended for developers who build
> Trio locally themselves. None of this has been tested against real hardware.

State of the dependencies (checked on 2026-11-18):

| Component | Version |
|---|---|
| Trio `main` | LoopKit submodule `loopandlearn/LoopKit` @ `f974241f5f25053d51da3e80833c85b13c387e6f` (branch `trio`) |
| OpenPatchKit | built and tested against exactly this LoopKit state (iOS simulator, Xcode 26.3) |
| Minimum iOS | 17.0 (Trio kits such as MedtrumKit use 17.5/17.6) |

There are two ways to connect the pod to Trio:

* **Option A, native:** Trio gets the new driver `OpenPatchKit` (this directory). Real values for reservoir, battery,
  reusable pod, 0.05 U granularity, pod sizes 70/100/200 U.
* **Option B, DASH compatibility mode:** The pod emulates Omnipod DASH. Trio stays **unmodified** and uses the existing `OmnipodKit`.

---

## Option A: Build OpenPatchKit in natively

### 0. What is in `ios/OpenPatchKit/`

```
OpenPatchKit/                 (directory ios/OpenPatchKit/)
├── OpenPatchKit.xcodeproj    generated, 3 frameworks + tests
├── OpenPatchCore/            pure Swift package (no LoopKit): units, state machine, wire v1, simulator
├── OpenPatchKit/             framework: OpenPatchPumpManager, state, transport (CoreBluetooth)
├── OpenPatchKitUI/           framework: setup (size, pair, fill, prime, attach), settings
├── OpenPatchKitTests/        XCTest against LoopKit + simulated pod
├── Support/                  umbrella header, Config.xcconfig (signing team)
└── scripts/                  generate_xcodeproj.rb, generate_strings.py
```

The Xcode project is generated. After changes to the file list, regenerate it (requires the `xcodeproj` gem from CocoaPods):

```bash
cd ios/OpenPatchKit
GEM_HOME=$(dirname $(dirname $(readlink -f $(which pod))))/libexec ruby scripts/generate_xcodeproj.rb
python3 scripts/generate_strings.py        # rewrite en/de Localizable.strings (aborts if a translation is missing)
```

### 1. Bring it into the Trio checkout as a submodule or directory

Trio expects each kit as a top-level directory with its own `.xcodeproj` (like `MedtrumKit/MedtrumKit.xcodeproj`).

**Option 1a, separate Git repository (clean, like the other kits):**

```bash
# in the ai-insulin-pump repo: split ios/OpenPatchKit off with its own history
git subtree split --prefix=ios/OpenPatchKit -b openpatchkit
git push git@github.com:<your-account>/OpenPatchKit.git openpatchkit:main

# in the Trio checkout
cd ~/dev/Trio
git submodule add https://github.com/<your-account>/OpenPatchKit.git OpenPatchKit
git submodule update --init --recursive
```

**Option 1b, purely local for trying it out (no remote):**

```bash
cd ~/dev/Trio
ln -s ~/dev/ai-insulin-pump/ios/OpenPatchKit OpenPatchKit      # or: cp -R ...
```

With the symlink, take care not to accidentally commit `OpenPatchKit` in Trio.

Optional, if you want to maintain the fork (analogous to `MedtrumKit`):

* `.gitmodules`: entry `[submodule "OpenPatchKit"] path = OpenPatchKit  url = https://github.com/<your-account>/OpenPatchKit.git`
* `scripts/define_common_trio.sh`: line `<your-account>:OpenPatchKit:main \` in the submodule list
* `scripts/swiftformat.sh`: `--exclude OpenPatchKit \`
* `.github/CODEOWNERS`: line `OpenPatchKit  @nightscout/trio-pump-codeowners`

### 2. Workspace entry

In `Trio.xcworkspace/contents.xcworkspacedata`, add next to `MedtrumKit`:

```xml
   <FileRef
      location = "group:OpenPatchKit/OpenPatchKit.xcodeproj">
   </FileRef>
```

Then open `Trio.xcworkspace`. The scheme `OpenPatchKit` and the targets `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI` must be visible.
The OpenPatch project resolves `LoopKit.framework` and `LoopKitUI.framework` via `BUILT_PRODUCTS_DIR` (like MedtrumKit). It can therefore **only be built
in the workspace**, not on its own.

### 3. Add the frameworks to the Trio app target

As with `MedtrumKit.framework` (see `Trio.xcodeproj`, phase "Embed Frameworks", `CodeSignOnCopy, RemoveHeadersOnCopy`):

1. Target **Trio** → *General* → *Frameworks, Libraries, and Embedded Content* → `+` →
   `OpenPatchCore.framework`, `OpenPatchKit.framework`, `OpenPatchKitUI.framework` (source: *Workspace*, project OpenPatchKit).
2. Set all three to **Embed & Sign**.
3. The order does not matter; `OpenPatchKitUI` depends on `OpenPatchKit` and `OpenPatchCore` (recorded in the project as target dependencies).

The app's `Info.plist`: Trio already has Bluetooth (`NSBluetoothAlwaysUsageDescription`, `UIBackgroundModes` with `bluetooth-central`). Do not add anything,
but verify it. Without `bluetooth-central` the app gets no background connection to the pod.

### 4. `DeviceCatalog.swift`: register the pump

File: `Trio/Sources/APS/Devices/DeviceCatalog.swift` (according to the file: "Adding a device means adding one entry to this file").

**4.1 Imports** (alphabetically among the other `import` lines):

```swift
import OpenPatchKit
import OpenPatchKitUI
```

`OpenPatchKitUI` is only needed for the `PumpManagerUI` conformance (like `MockKitUI`). It is declared via an extension in `OpenPatchKitUI`.

**4.2 Manufacturer section.** `OpenPatchPumpManager` has no entry in `DeviceManufacturer`. Either use the existing section `.otherSources`
or create your own:

```swift
enum DeviceManufacturer: CaseIterable {
    // ...
    case openPatch            // NEW
    // ...
    var displayName: String {
        switch self {
        // ...
        case .openPatch: return "OpenPatch"      // brand name, deliberately not localized
        }
    }
    // sortRank: 'default' returns 0, fits
}
```

**4.3 Entry in `DeviceCatalog.pumps`** (before the `MockPumpManager` entry):

```swift
PumpCatalogEntry(
    OpenPatchPumpManager.self,
    manufacturer: .openPatch,
    name: "OpenPatch (experimental)",
    supportedModels: ["OP-70", "OP-100", "OP-200"],
    icon: .none,                                   // no asset; fallback symbol "ivfluid.bag"
    basalCapability: BasalRateCapability(supportedRates: OpenPatchPumpManager.onboardingSupportedBasalRates),
    reportsRewindEvents: false                     // patch pump, nothing to rewind
),
```

* `id` is `OpenPatchPumpManager.pluginIdentifier` = `"OpenPatch"`. The pump state is persisted under this name. Do not change it again.
* `OpenPatchPumpManager.onboardingSupportedBasalRates` is a uniform grid 0.05…30 U/h (Trio checks uniformity in `DeviceCatalogTests`).
* `allowedInsulinTypes` stays at the default (`DeviceCatalog.defaultAllowedInsulinTypes`).

**4.4 Tests.** `TrioTests/DeviceCatalogTests.swift` checks catalog entries (including icons and basal grid). Cover the new entry there as well.

### 5. Optional: alert catalog

`Trio/Sources/Services/Alerts/AlertCatalogRegistry.swift` defines the alert level per pump. **OpenPatch works without an entry anyway**:
`TrioAlertManager` passes alerts without a catalog entry through unchanged (`podFault` is raised by the driver as `.critical`, the others as `.timeSensitive`).
If you want the alert levels to be configurable in Trio's "Device Alarms", add:

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

(`addEntry(manager, alertID, level, title, category, concept)`; concepts from `AlertCatalogVendor.swift`. `tempBasalCommLoss` has no suitable concept there,
`.unspecified` is also possible.)

### 6. Building and signing

* **Team:** `OpenPatchKit/Support/Config.xcconfig` takes `DEVELOPER_TEAM` from Trio's `ConfigOverride.xcconfig` (two or three levels above, `#include?`).
  This is the same file that, according to the Trio README, sets the team (`echo 'DEVELOPER_TEAM = XXXXXXXXXX' > ConfigOverride.xcconfig`).
  If it is missing, select the team in Xcode for the targets `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI` under *Signing & Capabilities* (Automatic Signing).
* **Bundle IDs** of the frameworks: `org.openpatch.OpenPatchCore|OpenPatchKit|OpenPatchKitUI`. Frameworks do not need their own App ID registration;
  embedding works with a free Apple account. If you want a different identifier, change `PRODUCT_BUNDLE_IDENTIFIER` in `scripts/generate_xcodeproj.rb`.
* **No entitlements** are needed in the frameworks. The Bluetooth permission and background mode belong to the app (see step 3).
* **Simulator:** The iOS simulator has no Bluetooth. In debug builds (`allowDebugFeatures`) the pairing screen offers
  "Use simulated pod (development)"; an in-memory pod then runs in real time (`OpenPatchSimulator`).
* **Build order:** On the first build, first `LoopKit`, then `OpenPatchCore`, `OpenPatchKit`, `OpenPatchKitUI`, then `Trio` (Xcode orders this itself via the target dependencies).

### 7. Verifying

```bash
# pure Swift, without the Xcode project, runs on macOS
cd ios/OpenPatchKit/OpenPatchCore && swift test

# driver against real LoopKit, on the simulator (workspace with LoopKit + OpenPatchKit required)
xcodebuild test -workspace Trio.xcworkspace -scheme OpenPatchKit \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' CODE_SIGNING_ALLOWED=NO
```

Then in Trio: *Settings → Pump → OpenPatch*. Setup flow: pod size → pair → fill (syringe, confirm amount) →
prime → attach to the cannula head → start. For later pod changes: Settings → "Remove pod from body" → "Refill and reuse pod".

### 7a. Application layer security: what the app has to wire up

`V1Transport(link:initialPhase:..., pairingSecret:)` already does the rest. The pieces that live in the Kit/UI layer:

1. **Pairing (once per pod):** the user presses the button on the pod (opens the 60 s window), the app connects and the BLE bond is made
   (CoreBluetooth shows the system dialog), then the app calls `transport.pair { result in ... }`. On success store the returned 32 bytes
   in the **Keychain** (`kSecClassGenericPassword`, `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`, one item per pod pair id / role), never in
   `rawState` / UserDefaults. On failure: `.sessionFailed` = window closed or altered exchange, ask the user to press the button again.
2. **Normal operation:** build the transport with `pairingSecret:` read from the Keychain (`OpenPatchPumpManager.makeV1Transport`). The first
   `send` of every connection runs the session handshake automatically (two extra round trips); the sequence counter restarts at 1.
3. **Errors:** `TransportError.notPaired` = the pod has no / another pairing secret (pod replaced, re-paired by someone else): show "pair again".
   `.sessionFailed` = wrong secret or an attacker in the middle: do not retry blindly, tell the user.
4. **Two-pod system:** every pod has its own pairing secret (pair A and pair B separately, store both).
5. **Optional out-of-band code:** `pair(oob:)` mixes a code both sides know into the exchange (makes the first pairing resistant to a
   man in the middle). The bench pod has no OOB source yet, so pass nothing.
6. `OpenPatchPumpManagerTests` / the simulator use `SimulatedTransport` and are unaffected.

On Linux (CI container) `swift test` in `OpenPatchCore` works without Xcode: Package.swift pulls in swift-crypto on non-Apple platforms (CryptoKit on iOS/macOS).
The LoopKit based Kit tests (`xcodebuild test`) need macOS/Xcode and cannot run on Linux. The Xcode project was regenerated (new source files; the
UUIDs changed because a newer `xcodeproj` gem was used).

### 8. Known gaps (honestly)

* **Never run against hardware.** `CoreBluetoothLink` compiles, but has only been tested against the protocol document and a fake firmware stub.
* **Security layer: implemented in `OpenPatchCore`, NOT yet wired into the PumpManager / setup UI.** Protocol v1.1 section 5.2
  (`docs/04-protocol.md`) defines an application layer key agreement; `V1Transport` implements the phone side
  (`SessionHandshake`, `SecureChannel`, `SessionCrypto`) and is byte-identical with the Rust pod (shared vectors
  `docs/vectors/session-key-agreement.json`, 24 tests in `swift test`). What the app still has to do (see the next section): create the
  pairing secret during pod setup, keep it in the Keychain, hand it to `V1Transport`, and show the pairing / "pair again" UI.
  Until then the driver sends plaintext frames, which only a `dev-plaintext` pod accepts. Replay protection: the command `seq` is
  per session (restarts at 1 with every handshake); `commandSequence` in `rawState` only matters for plaintext (dev) pods.

* **No push of alerts:** v1 has no alert characteristic. Alerts and bolus end arrive via `GetHistory` polling after each status read.
  The history cursor is persisted in `rawState` (`historyCursor`); events below the cursor are never delivered again (deduplication via the
  event ID), missed ones arrive exactly once after the restart. Delivery is at-least-once: if the app crashes between delivery and saving, an alert may arrive twice.
* **Bolus ID:** The pod does not assign a bolus ID; it is remembered in `V1Transport`. After an app restart during a bolus, the bolus is adopted as a foreign bolus.
* **Pod does not report a lifecycle phase:** `paired/filled/primed/…` is tracked by the app (`phaseHint`); the pod only knows `suspended`, `filled` and fault bits.
* **HUD/lifetime:** no tile for the Loop HUD (Trio does not use it), no expiry progress (reusable pod).
* **Temp basal duration** is rounded up on the wire to multiples of 30 min (spec 3.1); Loop sends multiples of 30 min anyway.
* **Alert levels** and texts are placeholders; the `Prime` amount (0.5 U) and fill limits (min. 10 U) must be adjusted after the first water test
  (`PumpConstants`, `PodSize`).

---

## Option B: DASH compatibility mode (no Trio change)

The pod emulates the Omnipod DASH BLE protocol (reference: `nightscout/ESP-Sim`, **GPL-3.0**, so the firmware part is then also GPL-3.0).
Trio sees a normal DASH pod and talks to it through the already integrated `OmnipodKit` (`OmniPumpManager`, catalog entry "Omnipod" with the models
"Classic, DASH, 5").

**What you do in Trio:** nothing at all in the code. No submodule, no workspace entry, no `DeviceCatalog` entry.

1. Flash the pod firmware in DASH mode (firmware team).
2. Trio → *Settings → Pump → Omnipod* (model DASH) → pair a new pod. The pod announces itself via BLE like a DASH pod.
3. Go through the normal Omnipod flow (fill, prime, insert cannula, start). The app behaves as it does with a DASH pod.

**What `OmnipodKit` expects from a DASH pod** (from `OmnipodKit/OmnipodCommon/Pod.swift`, branch `dev`) and what the OpenPatch pod therefore has to feign:

| DASH value in `OmnipodKit` | Value | Consequence for OpenPatch |
|---|---|---|
| Pulse size / bolus speed | 0.05 U, 2 s per pulse = 1.5 U/min | matches OpenPatch exactly (0.05 U, 1.5 U/min) |
| Reservoir capacity | 200 U | Trio always sees 200 U, even for OP-70/OP-100 |
| Reservoir display | exact values only below 50 U, above that "50+" (magic number 51.15) | A DASH pod reports no exact level above 50 U; native mode shows real values |
| Prime | 2.6 U at 1 s per pulse | the OpenPatch pod has no tubing to fill, only a 30G needle: firmware must accept the prime command, but deliver only the real dead volume (< 0.6 U), and keep the reservoir accounting accordingly |
| Insert cannula | 0.5 U | cannula is already in place (Insight Flex): acknowledge the command, deliver nothing |
| Lifetime | 80 h (`serviceDuration`), reminder 7 h before | Trio shows pod expiry after 80 h and demands a pod change: on every change, "re-pair" the pod, reset the pod state and refill |
| Basal profile | max. 24 entries, 30 min grid | pod must accept 24 segments |
| Temp basal | multiples of 30 min, up to 12 h; max. 30 U/h; max. bolus 30 U | the pod limits (10 U bolus, 5 U/h basal, 15 U/h total, see `spec/design-parameters.md` §7) are **stricter**; firmware then answers with an error that `OmnipodKit` shows as a rejected delivery. Therefore set the limits in Trio's settings (Max Bolus, Max Basal) equal or lower |
| Communication loss | DASH semantics: temp basal continues for max. 30 min | identical to the OpenPatch spec (§7) |

**Not supported:** Omnipod 5 (P-256/ECDSA-signed transcripts, key manager with App Attest), see `spec/design-parameters.md` §6.

**Which option when?** DASH mode is the fastest way to a test without a Trio change, but costs reservoir accuracy, pod size selection and the
reusable lifetime. Native mode (Option A) delivers real values, but needs the changes in this document and carries the risk of a
self-maintained Trio fork.

### 9. Two-pod system (A/B) and drive calibration

* **One pump for Trio.** `OpenPatchPumpManager` manages the pair A/B itself (spec/design-parameters.md section 1b): pair the first pod
  through the normal setup, then *Settings -> OpenPatch -> Pods A / B -> Pair spare pod*. Trio's status (reservoir, battery, doses, alerts)
  always comes from the active pod; each pod keeps its own reservoir, battery, wear time, dock state, drive calibration and wire sequence in
  `state.pair`.
* **Swap pod** (Settings): spare is checked (reachable, calibration, charged, filled) -> `Release` old pod -> user docks the new pod ->
  `Activate` (basal program + running temp basal) -> prime the cannula **connector only** (<= 0.52 U, no cannula prime) -> `Resume`.
  The state machine is `PairSwapCoordinator` (OpenPatchCore); its phase is persisted before every command that can leave the outcome unknown, so
  the screen resumes after a BLE loss or an app restart. Rules: never two active pods (no `Activate` before the old pod confirmed `Release` or
  the user confirmed it is physically removed - an undocked pod cannot deliver), a lost reply is resolved with a status read / idempotent resend,
  an uncertain prime is never retried blindly, a pod that reports itself active although it must not be is released at once.
* **Alerts:** wear 44 h (warning) / 52 h (stop), spare pod not charged / not filled / not seen, old pod unconfirmed, pod conflict, pod undocked.
* **Drive calibration.** There is no global "units per step" any more. The pod reports `DRIVE_CAL` in every `GetStatus`; the app accepts only the
  known drives (`DriveCalibration.known`: ZWBPD006006 5:1 = 0.0261 U/step, Faulhaber 16:1 = 0.0082 U/step) and refuses to pair-and-fill, prime, bolus,
  set a temp basal or resume with a pod that reports none or an unknown one (clear error in the UI). Suspend and cancel always work.
