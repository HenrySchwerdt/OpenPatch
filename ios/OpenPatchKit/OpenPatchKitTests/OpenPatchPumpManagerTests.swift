import HealthKit
import LoopKit
import OpenPatchCore
import XCTest
@testable import OpenPatchKit

final class OpenPatchPumpManagerTests: XCTestCase {
    private var pod: SimulatedPod!
    private var transport: SimulatedTransport!
    private var manager: OpenPatchPumpManager!
    private var delegate: TestPumpManagerDelegate!
    private let queue = DispatchQueue(label: "test.delegate")
    private var savedFactory: ((OpenPatchPumpManagerState) -> OpenPatchTransport)!

    override func setUp() {
        super.setUp()
        pod = SimulatedPod(size: .u200, startDate: Date())
        transport = SimulatedTransport(pod: pod)
        savedFactory = OpenPatchPumpManager.transportFactory
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []     // the tests resolve uncertainty themselves
        OpenPatchPumpManager.transportFactory = { [unowned self] _ in self.transport }
        var state = OpenPatchPumpManagerState()
        state.usesSimulatedPod = true
        state.basalSegments = [BasalSegment(startOffset: 0, unitsPerHour: 1.0)]
        manager = OpenPatchPumpManager(state: state, transport: transport)
        delegate = TestPumpManagerDelegate()
        manager.delegateQueue = queue
        manager.pumpManagerDelegate = delegate
    }

    override func tearDown() {
        OpenPatchPumpManager.transportFactory = savedFactory
        super.tearDown()
    }

    private func flush() { queue.sync {} }

    // MARK: helpers

    @discardableResult
    private func activate(fill: Double = 100) -> Error? {
        var failure: Error?
        manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true) { failure = failure ?? $0 }
        manager.confirmFill(units: fill) { failure = failure ?? $0 }
        manager.startPrime { failure = failure ?? $0 }
        transport.advance(by: Int(PumpConstants.primeDuration) + 1)
        manager.refreshStatus { failure = failure ?? $0 }
        manager.activate { failure = failure ?? $0 }
        flush()
        return failure
    }

    private func bolus(_ units: Double, type: BolusActivationType = .manualNoRecommendation) -> PumpManagerError? {
        var result: PumpManagerError?
        manager.enactBolus(units: units, activationType: type) { result = $0 }
        return result
    }

    // MARK: static capabilities

    func test_staticCapabilities_areNonEmptyAndOnTheFiveHundredthGrid() {
        let basal = OpenPatchPumpManager.onboardingSupportedBasalRates
        XCTAssertEqual(basal.first, 0.05)
        XCTAssertEqual(basal.last, 30)
        XCTAssertEqual(Set(zip(basal, basal.dropFirst()).map { ($1 - $0).rounded(toPlaces: 4) }).count, 1, "uniform grid (Trio BasalRateCapability requires it)")
        XCTAssertEqual(OpenPatchPumpManager.onboardingSupportedBolusVolumes.last, 25)
        XCTAssertEqual(OpenPatchPumpManager.onboardingMaximumBasalScheduleEntryCount, 24, "wire protocol v1 allows 24 segments")
        XCTAssertEqual(OpenPatchPumpManager.pluginIdentifier, "OpenPatch")
    }

    func test_rounding_neverExceedsRequest() {
        XCTAssertEqual(manager.roundToSupportedBolusVolume(units: 1.234), 1.2, accuracy: 1e-9)
        XCTAssertEqual(manager.roundToSupportedBolusVolume(units: 11.0), 11.0, accuracy: 1e-9, "no silent clamp to max bolus")
        XCTAssertEqual(manager.roundToSupportedBasalRate(unitsPerHour: 0.874), 0.85, accuracy: 1e-9)
        XCTAssertEqual(manager.supportedBolusVolumes.last, 10)
        XCTAssertEqual(manager.estimatedDuration(toBolus: 3), 120, accuracy: 1e-9)
    }

    // MARK: persistence

    func test_rawState_roundTrips() {
        var state = OpenPatchPumpManagerState()
        state.podSize = .u70
        state.phase = .active
        state.reservoirUnits = 42.5
        state.basalSegments = [BasalSegment(startOffset: 0, unitsPerHour: 0.9), BasalSegment(startOffset: 7200, unitsPerHour: 1.1)]
        state.unfinalizedBolus = OpenPatchDose(kind: .bolus, id: 3, units: 2, startDate: Date(timeIntervalSince1970: 100), duration: 80, automatic: false, insulinType: .fiasp)
        state.maxBolus = 7
        let restored = OpenPatchPumpManagerState(rawValue: state.rawValue)
        XCTAssertEqual(restored, state)
        XCTAssertNotNil(OpenPatchPumpManager(rawState: state.rawValue))
        XCTAssertNil(OpenPatchPumpManagerState(rawValue: ["version": 99, "state": Data()]))
        XCTAssertNil(OpenPatchPumpManagerState(rawValue: [:]))
    }

    // MARK: activation

    func test_activationFlow_endsActiveAndOnboarded() {
        XCTAssertNil(activate())
        XCTAssertEqual(manager.state.phase, .active)
        XCTAssertTrue(manager.isOnboarded)
        guard case .active? = manager.status.basalDeliveryState else { return XCTFail("\(String(describing: manager.status.basalDeliveryState))") }
        XCTAssertEqual(manager.status.bolusState, .noBolus)
        XCTAssertEqual(manager.state.reservoirUnits ?? 0, 99.5, accuracy: 0.1)
        XCTAssertEqual(manager.status.pumpBatteryChargeRemaining, 1.0)
        flush()
        XCTAssertTrue(delegate.events.contains { $0.type == .resume }, "activation is reported as a resume event")
        XCTAssertFalse(delegate.reservoirValues.isEmpty)
    }

    func test_fillOutsideRange_failsBeforeRadio() {
        manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true) { _ in }
        var error: Error?
        manager.confirmFill(units: 500) { error = $0 }
        XCTAssertEqual(error as? OpenPatchError, .fill(.tooLarge(maximum: 200)))
        XCTAssertEqual(pod.phase, .paired)
    }

    func test_activateWithoutBasalSchedule_fails() {
        var state = manager.state
        state.basalSegments = []
        let bare = OpenPatchPumpManager(state: state, transport: transport)
        var error: Error?
        bare.activate { error = $0 }
        XCTAssertEqual(error as? OpenPatchError, .notConfigured)
    }

    // MARK: bolus

    func test_bolus_isReportedMutableThenFinalizedFromPodEvent() {
        activate()
        let eventsBefore = delegate.events.count
        XCTAssertNil(bolus(2.0))
        flush()
        guard case .inProgress(let dose) = manager.status.bolusState else { return XCTFail("\(manager.status.bolusState)") }
        XCTAssertEqual(dose.programmedUnits, 2.0, accuracy: 1e-9)
        let inFlight = delegate.events.dropFirst(eventsBefore).last { $0.type == .bolus }
        XCTAssertEqual(inFlight?.dose?.isMutable, true)

        transport.advance(by: 90)    // 2 U take 80 s
        flush()
        XCTAssertEqual(manager.status.bolusState, .noBolus)
        let finished = delegate.events.last { $0.type == .bolus && $0.dose?.isMutable == false }
        XCTAssertEqual(finished?.dose?.deliveredUnits ?? 0, 2.0, accuracy: 1e-9)
        XCTAssertEqual(finished?.dose?.syncIdentifier, inFlight?.dose?.syncIdentifier, "same dose identity so the host replaces the mutable entry")
        XCTAssertEqual(pod.deliveredUnitsTotal, 2.0, accuracy: 0.1 + 1.0 * 90 / 3600 + 0.05)
    }

    func test_bolus_roundsDownToGrid() {
        activate()
        XCTAssertNil(bolus(1.234))
        guard case .inProgress(let dose) = manager.status.bolusState else { return XCTFail() }
        XCTAssertEqual(dose.programmedUnits, 1.2, accuracy: 1e-9)
    }

    func test_bolus_aboveConfiguredMaximum_isRejectedWithoutTouchingPod() {
        activate()
        let before = pod.deliveredUnitsTotal
        let error = bolus(11)
        guard case .configuration? = error else { return XCTFail("\(String(describing: error))") }
        XCTAssertEqual(pod.deliveredUnitsTotal, before, accuracy: 1e-9)
        XCTAssertEqual(manager.status.bolusState, .noBolus)
    }

    func test_secondBolusWhileRunning_isRejected() {
        activate()
        XCTAssertNil(bolus(3))
        guard case .deviceState? = bolus(1) else { return XCTFail() }
    }

    func test_bolusBeforeActivation_isRejected() {
        guard case .deviceState? = bolus(1) else { return XCTFail() }
    }

    func test_cancelBolus_returnsPartialDelivery() {
        activate()
        XCTAssertNil(bolus(3.0))     // 120 s
        transport.advance(by: 60)
        var result: PumpManagerResult<DoseEntry?>?
        manager.cancelBolus { result = $0 }
        guard case .success(let dose?)? = result else { return XCTFail("\(String(describing: result))") }
        XCTAssertEqual(dose.deliveredUnits ?? 0, 1.5, accuracy: 0.15)
        XCTAssertEqual(manager.status.bolusState, .noBolus)
        XCTAssertNil(pod.status.bolus)
    }

    func test_cancelBolusWithoutBolus_fails() {
        activate()
        var result: PumpManagerResult<DoseEntry?>?
        manager.cancelBolus { result = $0 }
        guard case .failure? = result else { return XCTFail() }
    }

    func test_bolusProgressReporter_existsWhileRunning() {
        activate()
        XCTAssertNil(manager.createBolusProgressReporter(reportingOn: queue))
        XCTAssertNil(bolus(3))
        let reporter = manager.createBolusProgressReporter(reportingOn: queue)
        XCTAssertNotNil(reporter)
        XCTAssertLessThan(reporter!.progress.percentComplete, 0.2)
    }

    // MARK: temp basal

    func test_tempBasal_setAndCancel() {
        activate()
        var error: PumpManagerError?
        manager.enactTempBasal(unitsPerHour: 2.0, for: 30 * 60) { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(pod.status.tempBasal?.rateTicks, 40)
        guard case .tempBasal(let dose)? = manager.status.basalDeliveryState else { return XCTFail() }
        XCTAssertEqual(dose.unitsPerHour, 2.0, accuracy: 1e-9)

        manager.enactTempBasal(unitsPerHour: 0, for: 0) { error = $0 }
        XCTAssertNil(error)
        XCTAssertNil(pod.status.tempBasal)
        guard case .active? = manager.status.basalDeliveryState else { return XCTFail() }
        flush()
        XCTAssertTrue(delegate.events.contains { $0.type == .tempBasal && $0.dose?.isMutable == false })
    }

    func test_tempBasal_aboveMax_isRejected() {
        activate()
        var error: PumpManagerError?
        manager.enactTempBasal(unitsPerHour: 6, for: 1800) { error = $0 }
        guard case .configuration? = error else { return XCTFail("\(String(describing: error))") }
    }

    func test_newTempBasal_replacesRunningOne() {
        activate()
        var error: PumpManagerError?
        manager.enactTempBasal(unitsPerHour: 2.0, for: 1800) { error = $0 }
        manager.enactTempBasal(unitsPerHour: 0.5, for: 1800) { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(pod.status.tempBasal?.rateTicks, 10)
        flush()
        XCTAssertEqual(delegate.events.filter { $0.type == .tempBasal && $0.dose?.isMutable == false }.count, 1, "old temp basal closed")
    }

    // MARK: suspend / resume

    func test_suspendResume() {
        activate()
        var error: Error?
        manager.suspendDelivery { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(pod.phase, .suspended)
        XCTAssertTrue(manager.status.basalDeliveryState?.isSuspended ?? false)
        guard case .deviceState? = bolus(1) else { return XCTFail("bolus while suspended must fail") }

        manager.resumeDelivery { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(pod.phase, .active)
        flush()
        XCTAssertTrue(delegate.events.contains { $0.type == .suspend })
        XCTAssertTrue(delegate.events.filter { $0.type == .resume }.count >= 2)
    }

    // MARK: settings

    func test_syncBasalRateSchedule_returnsScheduleAndStoresSegments() {
        activate()
        let items = [RepeatingScheduleValue(startTime: 0, value: 0.8), RepeatingScheduleValue(startTime: 6 * 3600, value: 1.2)]
        var result: Result<BasalRateSchedule, Error>?
        manager.syncBasalRateSchedule(items: items) { result = $0 }
        guard case .success(let schedule)? = result else { return XCTFail("\(String(describing: result))") }
        XCTAssertEqual(schedule.items.count, 2)
        XCTAssertEqual(manager.state.basalSegments.count, 2)
    }

    func test_syncBasalRateSchedule_rejectsMoreThan24Entries() {
        let items = (0..<30).map { RepeatingScheduleValue(startTime: Double($0) * 1800, value: $0 % 2 == 0 ? 1.0 : 1.5) }
        var result: Result<BasalRateSchedule, Error>?
        manager.syncBasalRateSchedule(items: items) { result = $0 }
        guard case .failure? = result else { return XCTFail() }
    }

    func test_syncBasalRateSchedule_rejectsRateAboveLimit() {
        var result: Result<BasalRateSchedule, Error>?
        manager.syncBasalRateSchedule(items: [RepeatingScheduleValue(startTime: 0, value: 9)]) { result = $0 }
        guard case .failure? = result else { return XCTFail() }
    }

    func test_syncDeliveryLimits_updatesLimitsAndSupportedVolumes() {
        activate()
        let limits = DeliveryLimits(maximumBasalRate: HKQuantity(unit: .internationalUnit().unitDivided(by: .hour()), doubleValue: 3),
                                    maximumBolus: HKQuantity(unit: .internationalUnit(), doubleValue: 4))
        var result: Result<DeliveryLimits, Error>?
        manager.syncDeliveryLimits(limits: limits) { result = $0 }
        guard case .success(let applied)? = result else { return XCTFail() }
        XCTAssertEqual(applied.maximumBolus?.doubleValue(for: .internationalUnit()), 4)
        XCTAssertEqual(manager.supportedBolusVolumes.last, 4)
        guard case .configuration? = bolus(4.5) else { return XCTFail() }
        XCTAssertNil(bolus(4))
    }

    // MARK: uncertain delivery

    func test_lostReply_marksDeliveryUncertain_thenPodStateIsAdopted() {
        activate()
        transport.fault = .dropResponse
        let error = bolus(1.5)
        guard case .uncertainDelivery? = error else { return XCTFail("\(String(describing: error))") }
        XCTAssertTrue(manager.status.deliveryIsUncertain)
        XCTAssertNotNil(pod.status.bolus, "the pod did execute the command")

        var syncError: Error?
        manager.refreshStatus { syncError = $0 }
        XCTAssertNil(syncError)
        XCTAssertFalse(manager.status.deliveryIsUncertain, "running bolus found on the pod resolves the uncertainty")
        guard case .inProgress = manager.status.bolusState else { return XCTFail() }
    }

    func test_notConnectedTransport_isConnectionErrorNotUncertain() {
        activate()
        transport.disconnect()
        let connectFails = FailingTransport()
        manager.replaceTransport(connectFails)
        let error = bolus(1)
        guard case .connection? = error else { return XCTFail("\(String(describing: error))") }
        XCTAssertFalse(manager.status.deliveryIsUncertain)
    }

    func test_clearDeliveryUncertainty() {
        activate()
        transport.fault = .dropResponse
        _ = bolus(1)
        manager.clearDeliveryUncertainty()
        XCTAssertFalse(manager.status.deliveryIsUncertain)
    }

    // MARK: pod events

    func test_lowReservoir_issuesAlert() {
        var state = manager.state
        state.basalSegments = [BasalSegment(startOffset: 0, unitsPerHour: 5.0)]
        manager = OpenPatchPumpManager(state: state, transport: transport)
        manager.delegateQueue = queue
        manager.pumpManagerDelegate = delegate
        activate(fill: 12)
        transport.advance(by: 3600)
        flush()
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "lowReservoir" })
        XCTAssertNotNil(manager.state.reservoirUnits)
    }

    func test_podFault_issuesCriticalAlertAndAlarmEvent() {
        activate()
        pod.injectFault(.occlusion)
        transport.advance(by: 1)
        flush()
        XCTAssertEqual(manager.state.phase, .faulted)
        XCTAssertNil(manager.status.basalDeliveryState)
        let alert = delegate.alerts.first { $0.identifier.alertIdentifier == "occlusion" }
        XCTAssertEqual(alert?.interruptionLevel, .critical, "an occlusion has its own critical alert")
        XCTAssertTrue(delegate.events.contains { $0.type == .alarm && $0.alarmType == .occlusion })
    }

    func test_otherFaults_keepTheGenericCriticalAlert_andAnEmptyPodHasItsOwn() {
        activate()
        pod.injectFault(.internalError)
        transport.advance(by: 1)
        flush()
        XCTAssertEqual(delegate.alerts.first { $0.identifier.alertIdentifier == "podFault" }?.interruptionLevel, .critical)
        manager.handle(event: .fault(.reservoirEmpty))
        flush()
        XCTAssertEqual(delegate.alerts.first { $0.identifier.alertIdentifier == "podEmpty" }?.interruptionLevel, .critical)
    }

    func test_tempBasalCommLossEvent_closesDose() {
        activate()
        var error: PumpManagerError?
        manager.enactTempBasal(unitsPerHour: 0, for: 3 * 3600) { error = $0 }
        XCTAssertNil(error)
        transport.advance(by: 31 * 60)
        flush()
        XCTAssertNil(manager.state.unfinalizedTempBasal)
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "tempBasalCommLoss" })
    }

    // MARK: deactivation / refill

    func test_deactivateThenRefill() {
        activate()
        var error: Error?
        manager.deactivatePod { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(manager.state.phase, .deactivated)
        XCTAssertNil(manager.status.basalDeliveryState)

        manager.beginRefill { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(manager.state.phase, .paired)
        manager.confirmFill(units: 150) { error = $0 }
        manager.startPrime { error = $0 }
        transport.advance(by: Int(PumpConstants.primeDuration) + 1)
        manager.refreshStatus { error = $0 }
        manager.activate { error = $0 }
        XCTAssertNil(error)
        XCTAssertEqual(manager.state.phase, .active)
    }

    func test_prepareForDeactivation_notifiesDelegate() {
        activate()
        let done = expectation(description: "deactivated")
        manager.prepareForDeactivation { error in
            XCTAssertNil(error)
            done.fulfill()
        }
        wait(for: [done], timeout: 2)
        XCTAssertEqual(pod.phase, .deactivated)
    }

    // MARK: sync

    func test_ensureCurrentPumpData_updatesLastSync() {
        activate()
        let before = manager.lastSync
        let done = expectation(description: "sync")
        var syncDate: Date?
        manager.ensureCurrentPumpData { syncDate = $0; done.fulfill() }
        wait(for: [done], timeout: 2)
        XCTAssertNotNil(syncDate)
        XCTAssertGreaterThanOrEqual(syncDate!, before ?? .distantPast)
    }
}

private final class FailingTransport: OpenPatchTransport {
    var isConnected = false
    var eventHandler: ((PodEvent) -> Void)?
    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { completion(.failure(.notConnected)) }
    func disconnect() {}
    func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) { completion(.failure(.notConnected)) }
}

private extension Double {
    func rounded(toPlaces places: Int) -> Double {
        let factor = pow(10.0, Double(places))
        return (self * factor).rounded() / factor
    }
}


// MARK: - Restart persistence of sequence number and history cursor

/// Answers every frame like a pod with an empty history at a configurable event id.
private final class StubPodLink: FrameLink {
    var isConnected = true
    var seqs: [UInt16] = []
    var nextEventID: UInt32 = 100
    var history: [V1.HistoryEvent] = []
    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { completion(.success(())) }
    func disconnect() {}
    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        let request = try! V1.decode(frame)
        seqs.append(request.seq)
        var tlvs = [V1.TLV(.result, u8: 0)]
        if request.type == V1.CommandID.getStatus.rawValue {
            tlvs += [V1.TLV(.stateFlags, u16: V1.StateFlags.suspended.rawValue), V1.TLV(.reservoirMU, u32: 50_000),
                     V1.TLV(.batteryMV, u16: 3800), V1.TLV(.nextEventID, u32: nextEventID)]
        } else if request.type == V1.CommandID.getHistory.rawValue {
            let from = request.u32(.fromID) ?? 0
            tlvs += history.filter { $0.id >= from }.map { V1.TLV(tag: V1.Tag.historyEvent.rawValue, value: $0.bytes) }
        }
        completion(.success(V1.encode(V1.Message(type: request.type | V1.responseFlag, flags: V1.flagResponse, seq: request.seq, tlvs: tlvs))))
    }
}

final class OpenPatchRestartPersistenceTests: XCTestCase {
    private var link: StubPodLink!
    private var savedFactory: ((OpenPatchPumpManagerState) -> OpenPatchTransport)!

    override func setUp() {
        super.setUp()
        link = StubPodLink()
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []
        savedFactory = OpenPatchPumpManager.transportFactory
        OpenPatchPumpManager.transportFactory = { [unowned self] state in OpenPatchPumpManager.makeV1Transport(state: state, link: self.link) }
    }

    override func tearDown() {
        OpenPatchPumpManager.transportFactory = savedFactory
        super.tearDown()
    }

    private func makeManager(from state: OpenPatchPumpManagerState) -> (OpenPatchPumpManager, TestPumpManagerDelegate) {
        let manager = OpenPatchPumpManager(state: state)
        let delegate = TestPumpManagerDelegate()
        manager.pumpManagerDelegate = delegate
        return (manager, delegate)
    }

    private func podState() -> OpenPatchPumpManagerState {
        var state = OpenPatchPumpManagerState()
        state.phase = .active
        state.isSetupCompleted = true
        return state
    }

    func test_rawState_roundTripsSequenceAndCursor() {
        var state = podState()
        state.commandSequence = 321
        state.historyCursor = 4711
        let restored = OpenPatchPumpManagerState(rawValue: state.rawValue)
        XCTAssertEqual(restored?.commandSequence, 321)
        XCTAssertEqual(restored?.historyCursor, 4711)
    }

    func test_oldRawStateWithoutNewFields_stillLoadsWithDefaults() throws {
        var raw = podState().rawValue
        var json = try JSONSerialization.jsonObject(with: raw["state"] as! Data) as! [String: Any]
        json.removeValue(forKey: "commandSequence"); json.removeValue(forKey: "historyCursor")
        raw["state"] = try JSONSerialization.data(withJSONObject: json)
        let restored = OpenPatchPumpManagerState(rawValue: raw)
        XCTAssertNotNil(restored)
        XCTAssertEqual(restored?.commandSequence, 1)
        XCTAssertNil(restored?.historyCursor)
    }

    func test_sequenceAndCursorAreWrittenIntoStateAsTheTransportRuns() {
        let (manager, _) = makeManager(from: podState())
        manager.refreshStatus { _ in }
        manager.refreshStatus { _ in }
        XCTAssertGreaterThan(manager.state.commandSequence, 2)
        XCTAssertEqual(manager.state.historyCursor, 100)
        XCTAssertEqual(OpenPatchPumpManagerState(rawValue: manager.rawState)?.historyCursor, 100)
    }

    func test_restart_neverReusesASequenceNumber() {
        let (first, _) = makeManager(from: podState())
        for _ in 0..<5 { first.refreshStatus { _ in } }
        let usedBefore = link.seqs
        let (second, _) = makeManager(from: OpenPatchPumpManagerState(rawValue: first.rawState)!)
        second.refreshStatus { _ in }
        XCTAssertGreaterThan(link.seqs.last!, usedBefore.max()!, "pod would drop a seq it already accepted")
        XCTAssertEqual(Set(link.seqs).count, link.seqs.count)
    }

    func test_restart_deliversMissedAlarmsOnceAndNotAgain() {
        let (first, firstDelegate) = makeManager(from: podState())
        first.refreshStatus { _ in }                      // cursor positioned at 100
        // app dies; pod logs a fault and a low-reservoir event meanwhile
        link.nextEventID = 102
        link.history = [V1.HistoryEvent(id: 100, timeSeconds: 1, type: V1.HistoryType.lowReservoir.rawValue, a: 9000, b: 0),
                        V1.HistoryEvent(id: 101, timeSeconds: 2, type: V1.HistoryType.fault.rawValue, a: Int32(V1.FaultBit.occlusion), b: 0)]
        _ = firstDelegate
        let saved = OpenPatchPumpManagerState(rawValue: first.rawState)!

        let (second, secondDelegate) = makeManager(from: saved)
        second.delegateQueue = DispatchQueue(label: "t2")
        secondDelegate.reset()
        second.refreshStatus { _ in }
        second.delegateQueue.sync {}
        XCTAssertEqual(secondDelegate.alerts.map(\.identifier.alertIdentifier).sorted(), ["lowReservoir", "occlusion"])
        XCTAssertEqual(second.state.historyCursor, 102)

        let (third, thirdDelegate) = makeManager(from: OpenPatchPumpManagerState(rawValue: second.rawState)!)
        third.delegateQueue = DispatchQueue(label: "t3")
        third.refreshStatus { _ in }
        third.delegateQueue.sync {}
        XCTAssertTrue(thirdDelegate.alerts.isEmpty, "events below the persisted cursor are not replayed")
    }
}
