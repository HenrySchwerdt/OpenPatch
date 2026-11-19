# Proposal 06: BLE privacy - resolvable private addresses, no static identifiers, minimal advertising

Status: proposed, **not implemented**. Priority **P1** (privacy is a stated asset: location and device presence via BLE).
Evidence: `firmware-rs/openpatch-bench/src/ble/mod.rs::device_address` and advertising.

## 1. What leaks today
1. `device_address()` derives a **static random address from FICR DEVICEADDR** (constant for the life of the device) and the advertised local name is `OpenPatch-XXXX` with the last 4 hex digits of that address. Any passive scanner can recognise this pod anywhere, at any time, for months: location tracking and "this person wears a pump" disclosure (health-data inference). Range with a Coded PHY long-range receiver is hundreds of metres.
2. The service UUID `2E092A48-506C-477E-ADD4-448BF149xxxx` in the advert makes the device class trivially identifiable (`OpenPatch` itself is a rare string, so detection is easy even without the address).
3. `PS_ID` (4 bytes, cleartext in `SESSION_INIT`, **static**) links all sessions of one pairing for anyone who sees the traffic content (FINDING-005; mitigation in proposal 03 section 5.4).
4. Distinguishable advertising state: pairing mode vs normal presumably changes the advert (needs verification in `ble/mod.rs`); that tells an attacker *exactly when* the 60 s window is open (a TOFU race trigger, see proposal 02).
5. Bond data holds the phone's IRK; fine.

## 2. Design
1. **Resolvable Private Address (RPA) for the pod** (LE Privacy 1.2): after bonding, the pod generates an RPA from its own IRK and rotates it every **15 minutes** (BLE default; configurable 1-15 min); the phone resolves it with the IRK it received at bonding. Only a *bonded peer* can link two advertising events. In the pairing window use a fresh **non-resolvable/RPA with a fresh random address per button press** (never the FICR address).
2. **Do not advertise the project name or a static UUID in the clear for bonded operation.** Normal operation uses **directed advertising** to the bonded phone's resolved identity (high duty cycle for the first 1.28 s, then low-duty directed or undirected with an empty payload and `ADV_IND` + Filter Accept List to the bonded phone only): a pod that only accepts connection requests from the bonded phone (controller-level `FilterAcceptList` with the phone's identity) and sends **no scannable** advertising otherwise. (trouble-host/SDC: `filter_accept_list`, `AdvertiseConfig::filter_policy`; verify support in the pinned versions. If not supported, implement `is_bonded_peer` disconnect immediately as today but keep the advert minimal: flags + 2-byte manufacturer ID? never the project name.)
3. **Pairing-mode advertising is indistinguishable in size and timing from normal**; the only observable difference is a short GATT flag readable *after* connection. This removes the "window is open now" beacon, at the price of requiring the app to attempt pairing explicitly (it knows from the user action). Alternatively, if the beacon must exist for UX, put a **rotating 4-byte token derived from the QR secret (proposal 02)** in the advert so only the holder of the label recognises the pod (privacy-preserving discovery, like Apple's Find My / Exposure Notification rolling identifiers).
4. **No device name characteristic** or a generic constant (`Pump`); no firmware version, serial or battery in any unauthenticated characteristic; serial appears only inside an authenticated session.
5. **Transmit power and PHY**: use the minimum power that works with the phone at body distance (nRF52840 default 0 dBm; try -8 dBm; measure RSSI at 1 m / 3 m) and **disable the Coded PHY (LE Long Range) for advertising** (extended advertising on Coded PHY gives the attacker 100 m+). Documented as a measurable control: `bench-testing.md` gets a range test (RSSI floor at 2 m, 5 m, 10 m behind a wall).
6. **Anti-tracking via connection intervals**: nothing special; do not expose a fixed-size periodic advertisement.
7. **Data minimisation on the wire**: `GetStatus` returns reservoir/battery only inside the encrypted session (already so; production refuses everything outside handshake).

## 3. Residual risk (state it)
RPA does not hide the *existence* of a BLE device from someone who sniffs advertising (they see a changing random address). Fingerprinting via radio characteristics (clock drift, transmit power, PHY timing) is possible in research settings and is out of scope. Timing correlation of the 15-minute rotation by an attacker who can see both addresses at the changeover is possible but weak.

## 4. Test plan
- Bench: BLE sniffer (nRF Sniffer on a second DK) for 1 h: assert no address repeats across rotations, no name, no UUID in the advert for bonded operation (script `security/privacy/check_adverts.py` to be written with the sniffer's pcap output).
- Unit tests in `openpatch-bench` (host-testable part): address generator never returns the FICR address; RPA structure (prand hash `ah(IRK, prand)`) test vectors from the BLE Core spec (Vol 3 Part H appendix D.7 sample data).
- Negative test: a second phone (not bonded) cannot connect (controller filter) and cannot even enumerate GATT.
- Document the TOFU-race effect of the pairing beacon in the usability notes (proposal 02 removes the need).
