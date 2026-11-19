import LoopKit
import OpenPatchCore
import XCTest
@testable import OpenPatchKit

/// PumpManager level: drive calibration gate and the A/B pod pair managed as ONE pump.
final class OpenPatchSwapTests: XCTestCase {
    private var podA: SimulatedPod!, podB: SimulatedPod!
    private var tA: SimulatedTransport!, tB: SimulatedTransport!
    private var manager: OpenPatchPumpManager!
    private var delegate: TestPumpManagerDelegate!
    private let queue = DispatchQueue(label: "test.delegate.swap")
    private var savedFactory: ((OpenPatchPumpManagerState) -> OpenPatchTransport)!
    private var savedPairFactory: ((OpenPatchPumpManagerState, PodRole) -> OpenPatchTransport)!

    override func setUp() {
        super.setUp()
        savedFactory = OpenPatchPumpManager.transportFactory
        savedPairFactory = OpenPatchPumpManager.pairTransportFactory
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []
        build(calibrationA: .zwbpd006006_5_1)
    }

    override func tearDown() {
        OpenPatchPumpManager.transportFactory = savedFactory
        OpenPatchPumpManager.pairTransportFactory = savedPairFactory
        super.tearDown()
    }

    private func build(calibrationA: DriveCalibration, reportsCalibrationA: Bool = true) {
        podA = SimulatedPod(size: .u200, startDate: Date(), calibration: calibrationA)
        podA.reportsCalibration = reportsCalibrationA
        podB = SimulatedPod(size: .u200, startDate: Date())
        tA = SimulatedTransport(pod: podA); tB = SimulatedTransport(pod: podB)
        OpenPatchPumpManager.transportFactory = { [unowned self] _ in self.tA }
        OpenPatchPumpManager.pairTransportFactory = { [unowned self] _, role in role == .a ? self.tA : self.tB }
        var state = OpenPatchPumpManagerState()
        state.usesSimulatedPod = true
        state.basalSegments = [BasalSegment(startOffset: 0, unitsPerHour: 1.0)]
        manager = OpenPatchPumpManager(state: state, transport: tA)
        delegate = TestPumpManagerDelegate()
        manager.delegateQueue = queue
        manager.pumpManagerDelegate = delegate
    }

    private func flush() { queue.sync {} }

    // MARK: helpers (the simulated transports answer synchronously)

    private func call(_ work: (@escaping (Error?) -> Void) -> Void) -> Error? {
        var result: Error?
        var done = false
        work { result = $0; done = true }
        XCTAssertTrue(done, "simulated transports complete synchronously")
        return result
    }

    private func activateA() {
        XCTAssertNil(call { self.manager.pair(peripheralIdentifier: nil, name: "A", simulated: true, completion: $0) })
        XCTAssertNil(call { self.manager.confirmFill(units: 150, completion: $0) })
        XCTAssertNil(call { self.manager.startPrime(completion: $0) })
        tA.advance(by: 45)
        XCTAssertNil(call { self.manager.refreshStatus(completion: $0) })
        XCTAssertNil(call { self.manager.activate(completion: $0) })
        flush()
    }

    private func readySpare() {
        XCTAssertNil(call { self.manager.pairSparePod(peripheralIdentifier: nil, name: "B", simulated: true, completion: $0) })
        XCTAssertNil(call { self.manager.fillSparePod(units: 200, completion: $0) })
        podB.setDocked(false)               // parked on the charger
        XCTAssertNil(call { self.manager.refreshSparePod(completion: $0) })
    }

    private var deliveringPods: Int { [podA!, podB!].filter { $0.isActivated && $0.isDocked && $0.phase == .active }.count }

    private func finishSwap() {
        for _ in 0..<10 where manager.state.pair?.phase != .idle {
            _ = call { self.manager.continueSwap(completion: $0) }
            tA.advance(by: 15); tB.advance(by: 15)
            XCTAssertLessThanOrEqual(deliveringPods, 1)
        }
    }

    // MARK: drive calibration gate

    func test_podWithoutCalibration_isRefusedAtPairing_andNothingCanBeFilledOrPrimed() {
        build(calibrationA: .zwbpd006006_5_1, reportsCalibrationA: false)
        let error = call { self.manager.pair(peripheralIdentifier: nil, name: "A", simulated: true, completion: $0) }
        XCTAssertEqual(error as? OpenPatchError, .calibration(.missing))
        XCTAssertNotNil(manager.state.calibrationBlock)
        XCTAssertEqual(call { self.manager.confirmFill(units: 100, completion: $0) } as? OpenPatchError, .calibration(.missing))
        XCTAssertEqual(call { self.manager.startPrime(completion: $0) } as? OpenPatchError, .calibration(.missing))
        XCTAssertEqual(podA.phase, .paired, "nothing was filled")
    }

    func test_podWithTheOldTenToOneCalibration_isRefused() {
        let old = DriveCalibration(driveID: 1, microUnitsPerStep: 13_100, stepsPerRevolution: 20, gearRatioTimes100: 1000)
        build(calibrationA: old)
        let error = call { self.manager.pair(peripheralIdentifier: nil, name: "A", simulated: true, completion: $0) }
        XCTAssertEqual(error as? OpenPatchError, .calibration(.unknown(driveID: 1, microUnitsPerStep: 13_100)))
        XCTAssertEqual(call { self.manager.startPrime(completion: $0) } as? OpenPatchError, .calibration(.unknown(driveID: 1, microUnitsPerStep: 13_100)))
    }

    func test_calibrationLostWhileRunning_blocksDeliveryButNotSuspend() {
        activateA()
        XCTAssertEqual(manager.state.phase, .active)
        XCTAssertNil(manager.state.calibrationBlock)
        podA.reportsCalibration = false                         // e.g. a pod that was reflashed with a firmware without DRIVE_CAL
        XCTAssertNil(call { self.manager.refreshStatus(completion: $0) })
        XCTAssertEqual(manager.state.calibrationProblem, .missing)
        var bolusError: PumpManagerError?
        manager.enactBolus(units: 1, activationType: .manualNoRecommendation) { bolusError = $0 }
        XCTAssertNotNil(bolusError)
        var tempError: PumpManagerError?
        manager.enactTempBasal(unitsPerHour: 1, for: 1800) { tempError = $0 }
        XCTAssertNotNil(tempError)
        XCTAssertNil(call { self.manager.suspendDelivery(completion: $0) }, "stopping is always allowed")
        let resumeError = call { self.manager.resumeDelivery(completion: $0) }
        XCTAssertNotNil(resumeError, "resuming needs a verified calibration")
        XCTAssertEqual(podA.phase, .suspended)
    }

    func test_validCalibrationAllowsTheWholeSetup() {
        activateA()
        XCTAssertEqual(manager.state.driveCalibration, .zwbpd006006_5_1)
        XCTAssertNil(manager.state.calibrationProblem)
        XCTAssertEqual(manager.state.phase, .active)
        XCTAssertEqual(manager.state.pair?.record(.a)?.calibration, .zwbpd006006_5_1)
    }

    // MARK: pair + swap

    func test_pairingBothPods_givesThemTheSamePairIDAndDifferentRoles() {
        activateA()
        readySpare()
        let pair = try! XCTUnwrap(manager.state.pair)
        XCTAssertEqual(pair.pods.count, 2)
        XCTAssertEqual(pair.active, .a)
        XCTAssertEqual(podA.pairID, pair.pairID)
        XCTAssertEqual(podB.pairID, pair.pairID)
        XCTAssertEqual(podA.role, .a)
        XCTAssertEqual(podB.role, .b)
        XCTAssertEqual(manager.state.podRole, .a)
        XCTAssertEqual(pair.record(.b)?.reservoirUnits ?? 0, 200, accuracy: 0.1)
        XCTAssertEqual(pair.record(.a)?.reservoirUnits ?? 0, 150 - 0.5, accuracy: 0.6)
    }

    func test_swap_trioSeesOnePump_statusFollowsTheActivePod() {
        activateA()
        readySpare()
        flush(); delegate.reset()
        XCTAssertNil(call { self.manager.beginSwap(completion: $0) })
        XCTAssertEqual(manager.state.pair?.phase, .awaitingDock)
        XCTAssertEqual(manager.state.phase, .deactivated, "between the pods nothing delivers")
        flush()
        XCTAssertTrue(delegate.events.contains { $0.type == .suspend }, "Trio is told delivery stopped")

        podA.setDocked(false); podB.setDocked(true)
        finishSwap()
        XCTAssertEqual(manager.state.pair?.phase, .idle)
        XCTAssertEqual(manager.state.pair?.active, .b)
        XCTAssertEqual(manager.state.podRole, .b)
        XCTAssertEqual(manager.state.phase, .active)
        guard case .active? = manager.status.basalDeliveryState else { return XCTFail("\(String(describing: manager.status.basalDeliveryState))") }
        XCTAssertEqual(manager.state.reservoirUnits ?? 0, podB.reservoirUnits, accuracy: 0.6, "reservoir shown to Trio is the active pod's")
        flush()
        XCTAssertTrue(delegate.events.contains { $0.type == .resume })
        // the spare is now A, with its own separate state
        XCTAssertEqual(manager.state.pair?.spare, .a)
        XCTAssertGreaterThan(manager.state.pair?.record(.a)?.wearSeconds ?? 0, 0)
        XCTAssertEqual(manager.state.pair?.record(.b)?.wearSeconds ?? 0, 0, accuracy: 120)

        // delivery commands now go to B
        XCTAssertNil(call { done in self.manager.suspendDelivery(completion: done) })
        XCTAssertEqual(podB.phase, .suspended)
        XCTAssertEqual(podA.phase, .deactivated)
    }

    func test_commandsAreRefusedWhileASwapRuns() {
        activateA()
        readySpare()
        XCTAssertNil(call { self.manager.beginSwap(completion: $0) })
        var error: PumpManagerError?
        manager.enactBolus(units: 1, activationType: .manualNoRecommendation) { error = $0 }
        XCTAssertNotNil(error)
        XCTAssertNotNil(call { self.manager.beginSwap(completion: $0) }, "no second swap while one is running")
    }

    func test_oldPodUnreachable_userMustConfirmRemoval_andThenTheSwapCompletes() {
        activateA()
        readySpare()
        flush(); delegate.reset()
        tA.isReachable = false
        let error = call { self.manager.beginSwap(completion: $0) }
        XCTAssertEqual(error as? OpenPatchError, .swap(.unreachable(.a)))
        XCTAssertEqual(manager.state.pair?.phase, .oldPodUnconfirmed)
        XCTAssertEqual(manager.state.phase, .active, "still believed active: we do not know")
        XCTAssertFalse(podB.isActivated)
        flush()
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "swapOldPodUnconfirmed" })

        // dock B anyway: still no activation
        podB.setDocked(true)
        _ = call { self.manager.continueSwap(completion: $0) }
        XCTAssertFalse(podB.isActivated)

        podA.setDocked(false)                                    // the user removes the old pod ...
        XCTAssertNil(manager.confirmOldPodPhysicallyRemoved())   // ... and says so
        XCTAssertEqual(manager.state.phase, .deactivated)
        finishSwap()
        XCTAssertEqual(manager.state.podRole, .b)
        XCTAssertEqual(manager.state.phase, .active)
        let level = podA.reservoirUnits
        tA.pod.advance(by: 3600)
        XCTAssertEqual(podA.reservoirUnits, level, "the old pod never heard of the release but it is undocked")
    }

    func test_spareNotReady_swapIsRefusedAndTheActivePodKeepsRunning() {
        activateA()
        XCTAssertNil(call { self.manager.pairSparePod(peripheralIdentifier: nil, name: "B", simulated: true, completion: $0) })
        XCTAssertNil(call { self.manager.fillSparePod(units: 30, completion: $0) })     // too little insulin
        let error = call { self.manager.beginSwap(completion: $0) }
        guard case .swap(.spareNotReady)? = error as? OpenPatchError else { return XCTFail("\(String(describing: error))") }
        XCTAssertEqual(manager.state.phase, .active)
        XCTAssertTrue(podA.isActivated)
    }

    func test_eachPodKeepsItsOwnWireSequence() {
        activateA()
        readySpare()
        let a = manager.state.pair?.record(.a), b = manager.state.pair?.record(.b)
        XCTAssertNotNil(a); XCTAssertNotNil(b)
        XCTAssertNotEqual(manager.pairTransports[.a] === manager.pairTransports[.b], true, "two transports")
    }

    // MARK: alerts

    func test_wearAlerts_andSpareNotReadyAlert() {
        activateA()
        readySpare()
        flush(); delegate.reset()
        podA.advance(by: 37 * 3600)                                // 37 h: the spare check starts
        podB.batteryPercent = 20
        XCTAssertNil(call { self.manager.refreshSparePod(completion: $0) })
        manager.ensureCurrentPumpData(completion: nil)
        flush()
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "spareNotReady" }, "\(delegate.alerts.map { $0.identifier.alertIdentifier })")
        XCTAssertFalse(delegate.alerts.contains { $0.identifier.alertIdentifier == "podWearWarning" })

        podA.advance(by: 8 * 3600)                                 // 45 h
        tA.advance(by: 0)
        manager.ensureCurrentPumpData(completion: nil)
        flush()
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "podWearWarning" })
        let warnings = delegate.alerts.filter { $0.identifier.alertIdentifier == "podWearWarning" }.count
        manager.ensureCurrentPumpData(completion: nil)
        flush()
        XCTAssertEqual(delegate.alerts.filter { $0.identifier.alertIdentifier == "podWearWarning" }.count, warnings, "raised once until it clears")
    }

    func test_undockEvent_cancelsTheBolusAndWarns() {
        activateA()
        var bolusError: PumpManagerError?
        manager.enactBolus(units: 2, activationType: .manualNoRecommendation) { bolusError = $0 }
        XCTAssertNil(bolusError)
        podA.setDocked(false)
        tA.advance(by: 1)
        flush()
        XCTAssertTrue(delegate.alerts.contains { $0.identifier.alertIdentifier == "podUndocked" })
        XCTAssertNil(manager.state.unfinalizedBolus)
    }

    func test_stateWithPairSurvivesRawStateRoundTrip() {
        activateA()
        readySpare()
        let restored = OpenPatchPumpManagerState(rawValue: manager.state.rawValue)
        XCTAssertEqual(restored?.pair, manager.state.pair)
        XCTAssertEqual(restored?.podRole, .a)
        XCTAssertEqual(restored?.driveCalibration, .zwbpd006006_5_1)
    }
}
