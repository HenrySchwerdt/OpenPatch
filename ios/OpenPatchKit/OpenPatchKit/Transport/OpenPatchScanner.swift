import CoreBluetooth
import Foundation

public struct DiscoveredPod: Identifiable, Equatable {
    public let id: UUID
    public let name: String
    public let rssi: Int
}

/// Scans for pods advertising the OpenPatch service. Used by the pairing screen.
public final class OpenPatchBluetoothScanner: NSObject, CBCentralManagerDelegate {
    private var central: CBCentralManager?
    private var found: [UUID: DiscoveredPod] = [:]
    private let queue = DispatchQueue(label: "org.openpatch.scanner")
    public var onUpdate: (([DiscoveredPod], CBManagerState) -> Void)?

    public override init() { super.init() }

    public func start() {
        queue.async {
            self.found.removeAll()
            if self.central == nil { self.central = CBCentralManager(delegate: self, queue: self.queue) }
            else if self.central?.state == .poweredOn { self.beginScan() }
        }
    }

    public func stop() {
        queue.async { self.central?.stopScan() }
    }

    private func beginScan() {
        central?.scanForPeripherals(withServices: [OpenPatchGATT.service], options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    public func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { beginScan() }
        onUpdate?(Array(found.values), central.state)
    }

    public func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                               advertisementData: [String: Any], rssi RSSI: NSNumber) {
        let name = (advertisementData[CBAdvertisementDataLocalNameKey] as? String) ?? peripheral.name ?? "OpenPatch"
        found[peripheral.identifier] = DiscoveredPod(id: peripheral.identifier, name: name, rssi: RSSI.intValue)
        onUpdate?(found.values.sorted { $0.rssi > $1.rssi }, central.state)
    }
}
