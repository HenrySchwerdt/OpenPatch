import CoreBluetooth
import Foundation
import OpenPatchCore

/// CoreBluetooth `FrameLink` for the OpenPatch pod (SKELETON: compiles, not yet exercised against hardware).
///
/// - connects to a bonded peripheral by identifier and discovers the OpenPatch service
/// - requires an ATT payload of at least 244 bytes (protocol v1 has no fragmentation)
/// - one frame per write; the response notification is matched to its request by `seq`
/// - unanswered requests complete with `.timeout` (the pod drops frames with errors silently)
public final class CoreBluetoothLink: NSObject, FrameLink, CBCentralManagerDelegate, CBPeripheralDelegate {
    private let queue = DispatchQueue(label: "org.openpatch.link")
    private var central: CBCentralManager!
    private let peripheralIdentifier: UUID?
    private var peripheral: CBPeripheral?
    private var commandCharacteristic: CBCharacteristic?
    private var ready = false
    private var connectCompletions: [(Result<Void, TransportError>) -> Void] = []
    private var connectTimeout: DispatchWorkItem?
    private var pending: [UInt16: (completion: (Result<Data, TransportError>) -> Void, timeout: DispatchWorkItem)] = [:]

    public var isConnected: Bool { queue.sync { ready } }

    public init(peripheralIdentifier: UUID?) {
        self.peripheralIdentifier = peripheralIdentifier
        super.init()
        central = CBCentralManager(delegate: self, queue: queue,
                                   options: [CBCentralManagerOptionRestoreIdentifierKey: OpenPatchGATT.restorationIdentifier])
    }

    // MARK: FrameLink

    public func connect(completion: @escaping (Result<Void, TransportError>) -> Void) {
        queue.async {
            if self.ready { return completion(.success(())) }
            self.connectCompletions.append(completion)
            guard self.connectCompletions.count == 1 else { return }   // an attempt is already running
            let timeout = DispatchWorkItem { [weak self] in self?.failConnect(.timeout) }
            self.connectTimeout = timeout
            self.queue.asyncAfter(deadline: .now() + OpenPatchGATT.connectTimeout, execute: timeout)
            self.startConnectionIfPossible()
        }
    }

    public func disconnect() {
        queue.async {
            if let peripheral = self.peripheral { self.central.cancelPeripheralConnection(peripheral) }
            self.teardown(error: .disconnected)
        }
    }

    public func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        queue.async {
            guard self.ready, let peripheral = self.peripheral, let characteristic = self.commandCharacteristic else {
                return completion(.failure(.notConnected))
            }
            guard peripheral.maximumWriteValueLength(for: .withoutResponse) >= frame.count else {
                return completion(.failure(.mtuTooSmall))
            }
            let timeout = DispatchWorkItem { [weak self] in
                self?.pending.removeValue(forKey: seq)?.completion(.failure(.timeout))
            }
            self.pending[seq] = (completion, timeout)
            self.queue.asyncAfter(deadline: .now() + OpenPatchGATT.responseTimeout, execute: timeout)
            peripheral.writeValue(frame, for: characteristic, type: .withResponse)
        }
    }

    // MARK: Connection handling (all on `queue`)

    private func startConnectionIfPossible() {
        switch central.state {
        case .poweredOn:
            if let id = peripheralIdentifier, let known = central.retrievePeripherals(withIdentifiers: [id]).first {
                attach(known)
            } else {
                central.scanForPeripherals(withServices: [OpenPatchGATT.service])
            }
        case .unauthorized, .unsupported, .poweredOff:
            failConnect(.bluetoothUnavailable)
        default:
            break   // `.unknown` / `.resetting`: wait for centralManagerDidUpdateState
        }
    }

    private func attach(_ candidate: CBPeripheral) {
        central.stopScan()
        peripheral = candidate
        candidate.delegate = self
        if candidate.state == .connected { candidate.discoverServices([OpenPatchGATT.service]) }
        else { central.connect(candidate, options: nil) }
    }

    private func failConnect(_ error: TransportError) {
        connectTimeout?.cancel()
        let completions = connectCompletions
        connectCompletions.removeAll()
        completions.forEach { $0(.failure(error)) }
    }

    private func finishConnect() {
        guard let peripheral, peripheral.maximumWriteValueLength(for: .withoutResponse) >= OpenPatchGATT.requiredWritePayload else {
            return failConnect(.mtuTooSmall)
        }
        ready = true
        connectTimeout?.cancel()
        let completions = connectCompletions
        connectCompletions.removeAll()
        completions.forEach { $0(.success(())) }
    }

    private func teardown(error: TransportError) {
        ready = false
        commandCharacteristic = nil
        let outstanding = pending
        pending.removeAll()
        outstanding.values.forEach { $0.timeout.cancel(); $0.completion(.failure(error)) }
        failConnect(error)
    }

    // MARK: CBCentralManagerDelegate

    public func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn, !connectCompletions.isEmpty { startConnectionIfPossible() }
        if central.state == .poweredOff || central.state == .unauthorized { teardown(error: .bluetoothUnavailable) }
    }

    public func centralManager(_ central: CBCentralManager, willRestoreState dict: [String: Any]) {
        if let restored = (dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral])?.first(where: { $0.identifier == peripheralIdentifier }) {
            peripheral = restored
            restored.delegate = self
        }
    }

    public func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                               advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard peripheralIdentifier == nil || peripheral.identifier == peripheralIdentifier else { return }
        attach(peripheral)
    }

    public func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([OpenPatchGATT.service])
    }

    public func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        failConnect(.disconnected)
    }

    public func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        teardown(error: .disconnected)
    }

    // MARK: CBPeripheralDelegate

    public func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let service = peripheral.services?.first(where: { $0.uuid == OpenPatchGATT.service }) else {
            return failConnect(.disconnected)
        }
        peripheral.discoverCharacteristics([OpenPatchGATT.commandCharacteristic, OpenPatchGATT.responseCharacteristic], for: service)
    }

    public func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil, let characteristics = service.characteristics,
              let command = characteristics.first(where: { $0.uuid == OpenPatchGATT.commandCharacteristic }),
              let response = characteristics.first(where: { $0.uuid == OpenPatchGATT.responseCharacteristic }) else {
            return failConnect(.disconnected)
        }
        commandCharacteristic = command
        peripheral.setNotifyValue(true, for: response)
    }

    public func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil else { return failConnect(.disconnected) }
        if characteristic.uuid == OpenPatchGATT.responseCharacteristic, characteristic.isNotifying { finishConnect() }
    }

    public func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.uuid == OpenPatchGATT.responseCharacteristic,
              let value = characteristic.value, value.count >= V1.headerSize else { return }
        let bytes = [UInt8](value)
        let seq = UInt16(bytes[3]) | UInt16(bytes[4]) << 8
        if let entry = pending.removeValue(forKey: seq) {
            entry.timeout.cancel()
            entry.completion(.success(value))
        }
    }
}
