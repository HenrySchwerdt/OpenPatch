import Foundation
import LoopKit
import OpenPatchCore
@testable import OpenPatchKit

/// Records everything the pump manager tells its delegate.
final class TestPumpManagerDelegate: PumpManagerDelegate {
    private let lock = NSLock()
    private var _events: [NewPumpEvent] = []
    private var _alerts: [Alert] = []
    private var _reservoir: [Double] = []
    private var _stateUpdates = 0
    private var _retracted: [String] = []

    var events: [NewPumpEvent] { lock.lock(); defer { lock.unlock() }; return _events }
    var alerts: [Alert] { lock.lock(); defer { lock.unlock() }; return _alerts }
    var reservoirValues: [Double] { lock.lock(); defer { lock.unlock() }; return _reservoir }
    var retractedAlerts: [String] { lock.lock(); defer { lock.unlock() }; return _retracted }
    var stateUpdates: Int { lock.lock(); defer { lock.unlock() }; return _stateUpdates }

    func reset() { lock.lock(); _events = []; _alerts = []; _reservoir = []; lock.unlock() }

    // DeviceManagerDelegate
    func deviceManager(_ manager: DeviceManager, logEventForDeviceIdentifier deviceIdentifier: String?, type: DeviceLogEntryType, message: String, completion: ((Error?) -> Void)?) { completion?(nil) }
    // AlertIssuer
    func issueAlert(_ alert: Alert) { lock.lock(); _alerts.append(alert); lock.unlock() }
    func retractAlert(identifier: Alert.Identifier) { lock.lock(); _retracted.append(identifier.alertIdentifier); lock.unlock() }
    // PersistedAlertStore
    func doesIssuedAlertExist(identifier: Alert.Identifier, completion: @escaping (Swift.Result<Bool, Error>) -> Void) { completion(.success(false)) }
    func lookupAllUnretracted(managerIdentifier: String, completion: @escaping (Swift.Result<[PersistedAlert], Error>) -> Void) { completion(.success([])) }
    func lookupAllUnacknowledgedUnretracted(managerIdentifier: String, completion: @escaping (Swift.Result<[PersistedAlert], Error>) -> Void) { completion(.success([])) }
    func recordRetractedAlert(_ alert: Alert, at date: Date) {}
    // PumpManagerStatusObserver
    func pumpManager(_ pumpManager: PumpManager, didUpdate status: PumpManagerStatus, oldStatus: PumpManagerStatus) {}
    // PumpManagerDelegate
    func pumpManagerBLEHeartbeatDidFire(_ pumpManager: PumpManager) {}
    func pumpManagerMustProvideBLEHeartbeat(_ pumpManager: PumpManager) -> Bool { false }
    func pumpManagerWillDeactivate(_ pumpManager: PumpManager) {}
    func pumpManagerPumpWasReplaced(_ pumpManager: PumpManager) {}
    func pumpManager(_ pumpManager: PumpManager, didUpdatePumpRecordsBasalProfileStartEvents pumpRecordsBasalProfileStartEvents: Bool) {}
    func pumpManager(_ pumpManager: PumpManager, didError error: PumpManagerError) {}
    func pumpManager(_ pumpManager: PumpManager, hasNewPumpEvents events: [NewPumpEvent], lastReconciliation: Date?, replacePendingEvents: Bool, completion: @escaping (Error?) -> Void) {
        lock.lock(); _events.append(contentsOf: events); lock.unlock()
        completion(nil)
    }
    func pumpManager(_ pumpManager: PumpManager, didReadReservoirValue units: Double, at date: Date, completion: @escaping (Result<(newValue: ReservoirValue, lastValue: ReservoirValue?, areStoredValuesContinuous: Bool), Error>) -> Void) {
        lock.lock(); _reservoir.append(units); lock.unlock()
    }
    func pumpManager(_ pumpManager: PumpManager, didAdjustPumpClockBy adjustment: TimeInterval) {}
    func pumpManagerDidUpdateState(_ pumpManager: PumpManager) { lock.lock(); _stateUpdates += 1; lock.unlock() }
    func pumpManager(_ pumpManager: PumpManager, didRequestBasalRateScheduleChange basalRateSchedule: BasalRateSchedule, completion: @escaping (Error?) -> Void) { completion(nil) }
    func startDateToFilterNewPumpEvents(for manager: PumpManager) -> Date { Date().addingTimeInterval(-3600) }
    var detectedSystemTimeOffset: TimeInterval { 0 }
    var automaticDosingEnabled: Bool { true }
}
