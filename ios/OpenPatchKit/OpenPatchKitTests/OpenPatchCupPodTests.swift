import LoopKit
import OpenPatchCore
import XCTest
@testable import OpenPatchKit

/// The cup pod from Trio's side, on the bench: assisted pressure fill, take-up prime, doses of SMB size, and everything that goes
/// wrong with a reply (uncertain delivery). The pod is the simulator with the cup drive (0x27, 0.007508 U per step).
final class OpenPatchCupPodTests: XCTestCase {
    private var pod: SimulatedPod!
    private var transport: SimulatedTransport!
    private var manager: OpenPatchPumpManager!
    private var delegate: TestPumpManagerDelegate!
    private let queue = DispatchQueue(label: "test.delegate.cup")
    private var savedFactory: ((OpenPatchPumpManagerState) -> OpenPatchTransport)!
    private let cup = DriveCalibration.nfp608_26_45_cup59Miter1_1

    override func setUp() {
        super.setUp()
        savedFactory = OpenPatchPumpManager.transportFactory
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []
        OpenPatchPumpManager.primeTakeupRetryDelay = 0.01
        build(calibration: cup)
    }

    override func tearDown() {
        OpenPatchPumpManager.transportFactory = savedFactory
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []
        OpenPatchPumpManager.primeTakeupRetryDelay = PumpConstants.primeTakeupRetryDelay
        OpenPatchPumpManager.commLossAlertAfter = 30 * 60
        super.tearDown()
    }

    private func build(calibration: DriveCalibration) {
        pod = SimulatedPod(size: .u100, startDate: Date(), calibration: calibration)
        transport = SimulatedTransport(pod: pod)
        OpenPatchPumpManager.transportFactory = { [unowned self] _ in self.transport }
        var state = OpenPatchPumpManagerState()
        state.usesSimulatedPod = true
        state.podSize = .u100
        state.basalSegments = [BasalSegment(startOffset: 0, unitsPerHour: 0.5)]
        manager = OpenPatchPumpManager(state: state, transport: transport)
        delegate = TestPumpManagerDelegate()
        manager.delegateQueue = queue
        manager.pumpManagerDelegate = delegate
    }

    private func flush() { queue.sync {} }

    private func call(_ work: (@escaping (Error?) -> Void) -> Void) -> Error? {
        var result: Error?
        var finished = false
        work { result = $0; finished = true }
        XCTAssertTrue(finished, "the simulated transport answers synchronously")
        return result
    }

    private func waitFor(_ description: String, timeout: TimeInterval = 3, _ condition: @escaping () -> Bool) {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.01)) }
        XCTAssertTrue(condition(), description)
    }

    /// Pairs, fills with the assisted pressure fill (pod off the dock), docks, primes and starts delivery.
    @discardableResult
    private func bringUp(fill units: Double = 20) -> Error? {
        pod.setDocked(false)
        if let error = call({ manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }) { return error }
        if let error = call({ manager.startFill(units: units, completion: $0) }) { return error }
        transport.advance(by: Int(units / cup.assistedFillUnitsPerSecond) + 3)
        _ = call { manager.refreshStatus(completion: $0) }
        pod.setDocked(true)
        let primed = expectation(description: "primed")
        var primeError: Error?
        manager.startPrime { primeError = $0; primed.fulfill() }
        wait(for: [primed], timeout: 3)
        if let primeError { return primeError }
        transport.advance(by: Int(PumpConstants.primeDuration) + 2)
        _ = call { manager.refreshStatus(completion: $0) }
        return call { manager.activate(completion: $0) }
    }

    private func bolus(_ units: Double, type: BolusActivationType = .automatic) -> PumpManagerError? {
        var result: PumpManagerError?
        manager.enactBolus(units: units, activationType: type) { result = $0 }
        return result
    }

    // MARK: fill

    func test_assistedFill_thenPrime_thenDelivery_endToEnd() {
        pod.setDocked(false)
        XCTAssertNil(call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) })
        XCTAssertEqual(manager.state.driveCalibration, cup)
        XCTAssertEqual(manager.allowedFillModes, [.assistedPressure])

        XCTAssertNil(call { manager.startFill(units: 20, completion: $0) })
        XCTAssertEqual(manager.state.fill?.state, .drawing, "the first status after the start already shows the job")
        transport.advance(by: 5)
        _ = call { manager.refreshStatus(completion: $0) }
        let midway = manager.state.fill
        XCTAssertEqual(midway?.drawnUnits ?? 0, 5 * cup.assistedFillUnitsPerSecond, accuracy: 0.01)
        XCTAssertEqual(manager.state.phase, .paired, "nothing is confirmed while the pod still retracts")

        transport.advance(by: 20)
        _ = call { manager.refreshStatus(completion: $0) }
        XCTAssertEqual(manager.state.fill?.state, .done)
        XCTAssertEqual(manager.state.phase, .filled)
        XCTAssertEqual(manager.state.reservoirUnits ?? 0, 20, accuracy: 0.06)

        pod.setDocked(true)
        let primed = expectation(description: "primed")
        manager.startPrime { XCTAssertNil($0); primed.fulfill() }
        wait(for: [primed], timeout: 3)
        transport.advance(by: Int(PumpConstants.primeDuration) + 2)
        _ = call { manager.refreshStatus(completion: $0) }
        XCTAssertEqual(manager.state.phase, .primed)
        XCTAssertNil(call { manager.activate(completion: $0) })
        XCTAssertEqual(manager.state.phase, .active)
        XCTAssertTrue(manager.isOnboarded)
    }

    func test_cupPod_neverDrawsBySuction_andRefusesTheManualFill() {
        pod.setDocked(false)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        let draw = call { manager.startFill(mode: .suctionDraw, units: 20, completion: $0) }
        XCTAssertEqual(draw as? OpenPatchError, .fillModeNotAllowed(.suctionDraw))
        let manual = call { manager.confirmFill(units: 20, completion: $0) }
        XCTAssertEqual(manual as? OpenPatchError, .fillModeNotAllowed(.manualConfirm))
        XCTAssertEqual(pod.phase, .paired)
        XCTAssertEqual(pod.reservoirUnits, 0, "nothing was asked of the pod")
        XCTAssertEqual(pod.status.fill?.state, .idle)
        XCTAssertEqual(draw?.localizedDescription.contains("no check valve"), true)
    }

    func test_legacyPod_keepsTheManualFill_andHasNoAssistedFill() {
        build(calibration: .zwbpd006006_5_1)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        XCTAssertEqual(manager.allowedFillModes, [.manualConfirm])
        XCTAssertEqual(call { manager.startFill(mode: .assistedPressure, units: 20, completion: $0) } as? OpenPatchError, .fillModeNotAllowed(.assistedPressure))
        XCTAssertNil(call { manager.startFill(units: 20, completion: $0) }, "default mode of a legacy pod: confirm the manual fill")
        XCTAssertEqual(manager.state.phase, .filled)
    }

    func test_fill_isRefusedWhileDocked_withTheRightReason() {
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }   // the pod starts docked
        let error = call { manager.startFill(units: 20, completion: $0) }
        XCTAssertEqual(error as? OpenPatchError, .rejected(.podDocked))
        XCTAssertEqual(pod.phase, .paired)
    }

    func test_fill_amountOutsideThePodsRange_failsBeforeTheRadio() {
        pod.setDocked(false)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        XCTAssertEqual(call { manager.startFill(units: 150, completion: $0) } as? OpenPatchError, .fill(.tooLarge(maximum: 100)))
        XCTAssertEqual(call { manager.startFill(units: 2, completion: $0) } as? OpenPatchError, .fill(.tooSmall(minimum: 10)))
        XCTAssertEqual(pod.status.fill?.state, .idle)
    }

    func test_aStalledFill_leavesWhatWasDrawn_andCanBeToppedUp() {
        pod.setDocked(false)
        pod.fillStallsAfterUnits = 8
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        _ = call { manager.startFill(units: 30, completion: $0) }
        transport.advance(by: 30)
        _ = call { manager.refreshStatus(completion: $0) }
        XCTAssertEqual(manager.state.fill?.state, .stalled)
        XCTAssertEqual(manager.state.fill?.drawnUnits ?? 0, 8, accuracy: 0.01)
        XCTAssertEqual(manager.state.phase, .filled)
        pod.fillStallsAfterUnits = nil
        XCTAssertNil(call { manager.startFill(units: 12, completion: $0) }, "a top-up is allowed in the filled phase")
        transport.advance(by: 20)
        _ = call { manager.refreshStatus(completion: $0) }
        XCTAssertEqual(manager.state.reservoirUnits ?? 0, 20, accuracy: 0.06)
    }

    func test_cancelFill_keepsWhatWasDrawn() {
        pod.setDocked(false)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        _ = call { manager.startFill(units: 40, completion: $0) }
        transport.advance(by: 4)
        XCTAssertNil(call { manager.cancelFill(completion: $0) })
        XCTAssertEqual(manager.state.fill?.state, .aborted)
        XCTAssertEqual(manager.state.fill?.drawnUnits ?? 0, 4 * cup.assistedFillUnitsPerSecond, accuracy: 0.01)
        XCTAssertEqual(manager.state.phase, .filled)
    }

    func test_unknownDrive_blocksTheFill() {
        build(calibration: DriveCalibration(driveID: 0x77, microUnitsPerStep: 7_030, stepsPerRevolution: 20, gearRatioTimes100: 2_645))
        pod.setDocked(false)
        let error = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        XCTAssertEqual(error as? OpenPatchError, .calibration(.unknown(driveID: 0x77, microUnitsPerStep: 7_030)))
        XCTAssertEqual(manager.allowedFillModes, [])
        XCTAssertEqual(call { manager.startFill(units: 20, completion: $0) } as? OpenPatchError, .calibration(.unknown(driveID: 0x77, microUnitsPerStep: 7_030)))
    }

    // MARK: prime with the take-up retry

    func test_prime_afterAnAssistedFill_repeatsWhenThePodAnswersHourly() {
        pod.setDocked(false)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        _ = call { manager.startFill(units: 20, completion: $0) }
        transport.advance(by: 20)
        _ = call { manager.refreshStatus(completion: $0) }
        pod.setDocked(true)
        pod.primeTakeupRejections = 2
        let primed = expectation(description: "primed after 3 attempts")
        manager.startPrime { XCTAssertNil($0); primed.fulfill() }
        wait(for: [primed], timeout: 3)
        XCTAssertEqual(pod.primeTakeupRejections, 0, "two slices of take-up, then the prime")
        XCTAssertNil(manager.state.primeTakeupAttempt)
        XCTAssertEqual(pod.phase, .priming)
    }

    func test_prime_givesUpAfterTheMaximumNumberOfAttempts() {
        pod.setDocked(false)
        _ = call { manager.pair(peripheralIdentifier: nil, name: "sim", simulated: true, completion: $0) }
        _ = call { manager.startFill(units: 20, completion: $0) }
        transport.advance(by: 20)
        _ = call { manager.refreshStatus(completion: $0) }
        pod.setDocked(true)
        pod.primeTakeupRejections = 100
        let failed = expectation(description: "gave up")
        manager.startPrime { error in
            XCTAssertEqual(error as? OpenPatchError, .rejected(.hourlyLimit))
            failed.fulfill()
        }
        wait(for: [failed], timeout: 3)
        XCTAssertEqual(100 - pod.primeTakeupRejections, PumpConstants.primeTakeupMaxAttempts)
        XCTAssertNil(manager.state.primeTakeupAttempt)
    }

    // MARK: SMB sized doses

    func test_smbSizedBoluses_areAcceptedOnTheGridAndDeliverTheirSum() {
        XCTAssertNil(bringUp(fill: 40))
        let before = pod.reservoirUnits
        for _ in 0..<20 {
            XCTAssertNil(bolus(0.05))
            transport.advance(by: 3)
            flush()
        }
        let basal = 0.5 / 3600 * 60       // the programmed 0.5 U/h also ran for the 60 simulated seconds
        XCTAssertEqual(before - pod.reservoirUnits, 1.0 + basal, accuracy: cup.unitsPerStep * 2.5, "20 x 0.05 U = 1.0 U within a step or two")
        let finished = delegate.events.filter { $0.type == .bolus && $0.dose?.isMutable == false }
        XCTAssertEqual(Set(finished.map(\.raw)).count, 20, "twenty distinct doses")
        XCTAssertTrue(finished.allSatisfy { abs(($0.dose?.programmedUnits ?? 0) - 0.05) < 1e-9 })
        XCTAssertEqual(manager.supportedBolusVolumes.first, 0.05)
        XCTAssertEqual(manager.roundToSupportedBolusVolume(units: 0.07), 0.05, accuracy: 1e-9)
    }

    func test_aBolusBelowTheGrid_isRefusedBeforeTheRadio() {
        XCTAssertNil(bringUp())
        let reservoir = pod.reservoirUnits
        guard case .configuration? = bolus(0.01) else { return XCTFail() }   // rounds down to 0.00 U
        XCTAssertEqual(pod.reservoirUnits, reservoir)
    }

    // MARK: uncertain delivery

    func test_aLostBolusReply_theBolusRanAndFinished_isRecoveredFromTheHistory() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        guard case .uncertainDelivery? = bolus(0.05) else { return XCTFail("must report uncertain delivery") }
        XCTAssertTrue(manager.status.deliveryIsUncertain)
        XCTAssertNotNil(manager.state.pendingCommand)
        transport.advance(by: 5)                          // the pod ran the 0.05 U bolus and logged its start and its end
        var syncError: Error?
        manager.refreshStatus { syncError = $0 }
        XCTAssertNil(syncError)
        flush()
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        XCTAssertNil(manager.state.pendingCommand)
        let reported = delegate.events.filter { $0.type == .bolus && $0.dose?.isMutable == false }
        // finished doses are replayed until the host confirms; the stable raw identifier is what Trio de-duplicates on
        XCTAssertEqual(Set(reported.map(\.raw)).count, 1, "the bolus is in Trio's history exactly once")
        XCTAssertEqual(reported.first?.dose?.programmedUnits ?? 0, 0.05, accuracy: 1e-9)
        XCTAssertEqual(reported.first?.dose?.automatic, true, "an SMB stays an automatic dose")
    }

    func test_aLostBolusReply_theBolusStillRuns_isAdoptedAsRunning() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        _ = bolus(2.0)
        let sync = call { manager.refreshStatus(completion: $0) }
        XCTAssertNil(sync)
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        guard case .inProgress(let dose) = manager.status.bolusState else { return XCTFail("\(manager.status.bolusState)") }
        XCTAssertEqual(dose.programmedUnits, 2.0, accuracy: 1e-9)
        transport.advance(by: 90)
        flush()
        XCTAssertEqual(Set(delegate.events.filter { $0.type == .bolus && $0.dose?.isMutable == false }.map(\.raw)).count, 1)
    }

    func test_aBolusThatNeverReachedThePod_isRecognisedAsNotDelivered() {
        XCTAssertNil(bringUp())
        let reservoir = pod.reservoirUnits
        transport.fault = .dropRequest
        guard case .uncertainDelivery? = bolus(1.0) else { return XCTFail() }
        XCTAssertTrue(manager.status.deliveryIsUncertain, "from the outside it looks the same")
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        XCTAssertFalse(manager.status.deliveryIsUncertain, "the pod's history shows no bolus: it was not delivered")
        XCTAssertNil(manager.state.unfinalizedBolus)
        flush()
        XCTAssertTrue(delegate.events.filter { $0.type == .bolus }.isEmpty, "no phantom dose in Trio's history")
        XCTAssertEqual(pod.reservoirUnits, reservoir, accuracy: cup.unitsPerStep)
    }

    func test_noSecondBolus_whileTheFirstIsUnresolved() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        _ = bolus(1.0)
        guard case .uncertainDelivery? = bolus(0.5) else { return XCTFail("a second bolus must be blocked") }
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        guard case .deviceState? = bolus(0.5) else { return XCTFail("the first bolus really runs: now it is simply busy") }
        transport.advance(by: 60)
        flush()
        XCTAssertNil(bolus(0.05), "after the resolution (and the end of the first bolus) boluses work again")
    }

    func test_aLostTempBasalReply_isRecoveredBothWays() {
        XCTAssertNil(bringUp())
        var error: PumpManagerError?
        transport.fault = .dropResponse
        manager.enactTempBasal(unitsPerHour: 1.5, for: 1800) { error = $0 }
        guard case .uncertainDelivery? = error else { return XCTFail("\(String(describing: error))") }
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        guard case .tempBasal(let dose)? = manager.status.basalDeliveryState else { return XCTFail("\(String(describing: manager.status.basalDeliveryState))") }
        XCTAssertEqual(dose.unitsPerHour, 1.5, accuracy: 1e-9)

        // and a temp basal that never arrived
        manager.enactTempBasal(unitsPerHour: 0, for: 0) { _ in }
        transport.fault = .dropRequest
        manager.enactTempBasal(unitsPerHour: 2.5, for: 1800) { error = $0 }
        guard case .uncertainDelivery? = error else { return XCTFail() }
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        guard case .active? = manager.status.basalDeliveryState else { return XCTFail("\(String(describing: manager.status.basalDeliveryState))") }
    }

    func test_aLostSuspendReply_isResolvedByTheStatusAndReported() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        let error = call { manager.suspendDelivery(completion: $0) }
        guard case .uncertainDelivery? = error as? PumpManagerError else { return XCTFail("\(String(describing: error))") }
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        flush()
        XCTAssertFalse(manager.status.deliveryIsUncertain)
        XCTAssertEqual(manager.state.phase, .suspended)
        XCTAssertTrue(delegate.events.contains { $0.type == .suspend }, "the suspend that the pod did execute is in Trio's history")
    }

    func test_aLostBasalProgramReply_isResolvedBySendingItAgain() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        var result: Result<BasalRateSchedule, Error>?
        manager.syncBasalRateSchedule(items: [RepeatingScheduleValue(startTime: 0, value: 0.7)]) { result = $0 }
        guard case .failure? = result else { return XCTFail() }
        XCTAssertTrue(manager.status.deliveryIsUncertain)
        XCTAssertNil(call { manager.refreshStatus(completion: $0) })
        waitFor("the idempotent resend settled it") { !self.manager.status.deliveryIsUncertain }
        XCTAssertNil(manager.state.pendingCommand)
    }

    func test_theManagerFindsOutOnItsOwn_withoutAnyoneAskingForAStatus() {
        OpenPatchPumpManager.uncertaintyRecoveryDelays = [0.01, 0.01, 0.01]
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        _ = bolus(0.05)
        XCTAssertTrue(manager.status.deliveryIsUncertain)
        waitFor("automatic recovery read") { !self.manager.status.deliveryIsUncertain }
        XCTAssertNotNil(manager.state.unfinalizedBolus, "the bolus the pod started is adopted (it is still running in simulated time)")
        XCTAssertNil(manager.state.pendingCommand)
    }

    func test_theUncertaintySurvivesARestart() {
        XCTAssertNil(bringUp())
        transport.fault = .dropResponse
        _ = bolus(0.05)
        let restored = OpenPatchPumpManagerState(rawValue: manager.rawState)
        XCTAssertNotNil(restored?.deliveryUncertainSince)
        XCTAssertEqual(restored?.pendingCommand?.kind, manager.state.pendingCommand?.kind)
    }

    // MARK: alerts

    func test_noContactAlert_isRaisedOnceAfterTheLimit_andRetractedWhenTheContactIsBack() {
        XCTAssertNil(bringUp())
        OpenPatchPumpManager.commLossAlertAfter = 0
        transport.isReachable = false
        let first = expectation(description: "sync 1"), second = expectation(description: "sync 2")
        manager.ensureCurrentPumpData { _ in first.fulfill() }
        wait(for: [first], timeout: 2)
        manager.ensureCurrentPumpData { _ in second.fulfill() }
        wait(for: [second], timeout: 2)
        flush()
        XCTAssertEqual(delegate.alerts.filter { $0.identifier.alertIdentifier == "commLoss" }.count, 1, "once, not on every failed read")
        transport.isReachable = true
        let third = expectation(description: "sync 3")
        manager.ensureCurrentPumpData { _ in third.fulfill() }
        wait(for: [third], timeout: 2)
        flush()
        XCTAssertEqual(delegate.retractedAlerts, ["commLoss"])
    }

    func test_podExpiryWarnings_andNotDocked_stillAlert() {
        XCTAssertNil(bringUp())
        manager.handle(event: .wearWarning)
        manager.handle(event: .wearExpired)
        manager.handle(event: .docked(false))
        manager.handle(event: .lowReservoir(pulses: 100))
        flush()
        let ids = Set(delegate.alerts.map(\.identifier.alertIdentifier))
        XCTAssertTrue(ids.isSuperset(of: ["podWearWarning", "podWearExpired", "podUndocked", "lowReservoir"]), "\(ids)")
    }
}
