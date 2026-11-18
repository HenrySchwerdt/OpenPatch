import XCTest
@testable import OpenPatchCore

/// A/B swap state machine against two simulated pods. The central invariant is checked after EVERY step:
/// never two pods that are activated, docked and running at the same time.
final class PairSwapTests: XCTestCase {
    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)
    private let pairID: UInt32 = 0x0BAD_CAFE

    private var podA: SimulatedPod!, podB: SimulatedPod!
    private var tA: SimulatedTransport!, tB: SimulatedTransport!
    private var coordinator: PairSwapCoordinator!
    private var saved: [PodPairState] = []
    private var events: [PairEvent] = []
    private var tempBasal: (rateTicks: UInt16, end: Date)?
    private var program: BasalProgram!
    private var clock: Date { podA.now }

    override func setUpWithError() throws {
        program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 1.0)])
        podA = SimulatedPod(size: .u100, startDate: t0)
        podB = SimulatedPod(size: .u100, startDate: t0)
        for (pod, role) in [(podA!, PodRole.a), (podB!, PodRole.b)] {
            _ = pod.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
            _ = pod.handle(.setPairing(pairID: pairID, role: role))
            _ = pod.handle(.confirmFill(pulses: 2000))
        }
        // A is on the body and delivering; B sits on the charger (undocked).
        _ = podA.handle(.activatePod(pairID: pairID, activationID: 100, program: program, tempBasal: nil))
        _ = podA.handle(.prime)
        podA.advance(by: 41); podB.advance(by: 41)
        _ = podA.handle(.confirmAttached)
        podB.setDocked(false)
        tA = SimulatedTransport(pod: podA); tB = SimulatedTransport(pod: podB)
        try rebuildCoordinator(state: nil)
        coordinator.state.update(.a) { $0.lastSeen = t0 }
        coordinator.state.update(.b) { $0.lastSeen = t0; $0.batteryFraction = 1.0; $0.reservoirUnits = 100 }
    }

    private func rebuildCoordinator(state: PodPairState?) throws {
        let initial = state ?? PodPairState(pairID: pairID, pods: [PodRecord(role: .a, size: .u100), PodRecord(role: .b, size: .u100)], active: .a)
        coordinator = PairSwapCoordinator(state: initial, transports: [.a: tA, .b: tB], clock: { [unowned self] in clock },
                                          context: { [unowned self] in SwapContext(program: program, tempBasal: tempBasal) })
        coordinator.stateHandler = { [unowned self] in saved.append($0) }
        coordinator.eventHandler = { [unowned self] in events.append($0) }
    }

    // MARK: helpers

    /// Pods that are activated, docked and in the delivering phase.
    private var deliveringPods: [PodRole] {
        [(PodRole.a, podA!), (.b, podB!)].filter { $0.1.isActivated && $0.1.isDocked && $0.1.phase == .active }.map(\.0)
    }

    /// Off only in the one test that models a user who confirms a wrong "pod removed".
    private var enforceSingleDeliverer = true

    private func assertSingleDeliverer(_ message: String = "", file: StaticString = #filePath, line: UInt = #line) {
        guard enforceSingleDeliverer else { return }
        XCTAssertLessThanOrEqual(deliveringPods.count, 1, "two pods deliver at once! \(message)", file: file, line: line)
    }

    enum Outcome: Equatable { case ok; case failed(SwapFailure) }

    private func outcome(_ r: Result<Void, SwapFailure>) -> Outcome {
        switch r { case .success: return .ok; case .failure(let f): return .failed(f) }
    }

    @discardableResult
    private func run(_ body: (@escaping (Result<Void, SwapFailure>) -> Void) -> Void, file: StaticString = #filePath, line: UInt = #line) -> Outcome {
        var result: Result<Void, SwapFailure>!
        body { result = $0 }
        assertSingleDeliverer(file: file, line: line)
        return outcome(result)
    }

    private func begin() -> Outcome { run { self.coordinator.begin(completion: $0) } }
    private func resume() -> Outcome { run { self.coordinator.resume(completion: $0) } }

    private func physicallySwap() { podA.setDocked(false); podB.setDocked(true) }

    /// Drives `resume()` with pod time passing (the simulated prime takes 40 s) until the swap is done.
    private func finishSwap(file: StaticString = #filePath, line: UInt = #line) {
        for _ in 0..<12 where coordinator.state.phase != .idle {
            _ = resume()
            podA.advance(by: 15); podB.advance(by: 15)
            assertSingleDeliverer(file: file, line: line)
        }
        XCTAssertEqual(coordinator.state.phase, .idle, file: file, line: line)
    }

    // MARK: happy path

    func test_happyPath_releaseDockActivatePrimeResume() {
        let phases = { self.events.compactMap { e -> SwapPhase? in if case .phaseChanged(let p) = e { return p }; return nil } }
        XCTAssertEqual(begin(), .ok)
        XCTAssertEqual(coordinator.state.phase, .awaitingDock)
        XCTAssertEqual(coordinator.state.oldPodSafety, .releasedConfirmed)
        XCTAssertNil(coordinator.state.active, "between release and activation nobody delivers")
        XCTAssertFalse(podA.isActivated)
        XCTAssertNotNil(coordinator.state.lastRelease)

        // the new pod is still on the charger: no activation, nothing changes
        XCTAssertEqual(resume(), .failed(.notDocked(.b)))
        XCTAssertFalse(podB.isActivated)
        XCTAssertEqual(coordinator.state.phase, .awaitingDock)

        physicallySwap()
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
        XCTAssertEqual(podB.phase, .active)
        XCTAssertTrue(podB.isActivated)
        XCTAssertFalse(podA.isActivated)
        XCTAssertEqual(phases(), [.releasingOld, .awaitingDock, .activatingNew, .priming, .resuming, .idle])
        XCTAssertTrue(events.contains(.swapCompleted(newActive: .b)))
        XCTAssertEqual(coordinator.state.spare, .a)
        // after the swap B delivers and A does not
        let a = podA.reservoirUnits, b = podB.reservoirUnits
        podA.advance(by: 3600); podB.advance(by: 3600)
        XCTAssertEqual(podA.reservoirUnits, a)
        XCTAssertLessThan(podB.reservoirUnits, b)
    }

    func test_pods_keepSeparateReservoirBatteryAndWearState() {
        podA.batteryPercent = 80; podB.batteryPercent = 55
        podA.advance(by: 3 * 3600); podB.advance(by: 3 * 3600)
        _ = run { self.coordinator.resume(completion: $0) }
        tA.connect { _ in }; tB.connect { _ in }
        var a: PodStatus!, b: PodStatus!
        tA.send(.getStatus) { if case .success(.ok(let s)) = $0 { a = s } }
        tB.send(.getStatus) { if case .success(.ok(let s)) = $0 { b = s } }
        coordinator.observe(.a, status: a)
        coordinator.observe(.b, status: b)
        let recA = coordinator.state.record(.a)!, recB = coordinator.state.record(.b)!
        XCTAssertEqual(recA.batteryFraction, 0.8)
        XCTAssertEqual(recB.batteryFraction, 0.55)
        XCTAssertEqual(Double(recA.wearSeconds ?? 0), 3 * 3600, accuracy: 120)   // + the 41 s of setup
        XCTAssertEqual(recB.wearSeconds, 0, "the spare does not wear")
        XCTAssertLessThan(recA.reservoirUnits!, 99.6)
        XCTAssertEqual(recB.reservoirUnits!, 100, accuracy: 0.05)
        XCTAssertEqual(recA.isDocked, true)
        XCTAssertEqual(recB.isDocked, false)
    }

    // MARK: the spare must be able to take over BEFORE the old pod is touched

    func test_spareNotCharged_blocksTheSwapAndLeavesTheActivePodAlone() {
        podB.batteryPercent = 30
        coordinator.state.update(.b) { $0.batteryFraction = 0.3 }
        guard case .failed(.spareNotReady(let problems)) = begin() else { return XCTFail() }
        XCTAssertTrue(problems.contains { if case .notCharged = $0 { return true }; return false })
        XCTAssertEqual(coordinator.state.phase, .idle)
        XCTAssertTrue(podA.isActivated, "old pod untouched")
    }

    func test_spareNotFilled_blocksTheSwap() {
        let low = SimulatedPod(size: .u100, startDate: t0)
        _ = low.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
        _ = low.handle(.setPairing(pairID: pairID, role: .b))
        _ = low.handle(.confirmFill(pulses: 400))   // 20 U
        tB = SimulatedTransport(pod: low)
        try? rebuildCoordinator(state: coordinator.state)
        guard case .failed(.spareNotReady(let problems)) = begin() else { return XCTFail() }
        XCTAssertTrue(problems.contains { if case .notFilled = $0 { return true }; return false })
        XCTAssertEqual(coordinator.state.phase, .idle)
        XCTAssertTrue(podA.isActivated)
    }

    func test_spareWithUnknownOrMissingCalibration_blocksTheSwap() {
        for calibration in [Optional(DriveCalibration(driveID: 1, microUnitsPerStep: 13_100, stepsPerRevolution: 20, gearRatioTimes100: 1000)), nil] {
            let spare = SimulatedPod(size: .u100, startDate: t0, calibration: calibration ?? .zwbpd006006_5_1)
            spare.reportsCalibration = calibration != nil && false
            _ = spare.handle(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0))
            _ = spare.handle(.setPairing(pairID: pairID, role: .b))
            _ = spare.handle(.confirmFill(pulses: 2000))
            tB = SimulatedTransport(pod: spare)
            try? rebuildCoordinator(state: PodPairState(pairID: pairID, pods: coordinator.state.pods, active: .a))
            coordinator.state.update(.b) { $0.lastSeen = t0; $0.batteryFraction = 1; $0.reservoirUnits = 100 }
            guard case .failed(.calibration(.b, _)) = begin() else { return XCTFail("calibration \(String(describing: calibration))") }
            XCTAssertEqual(coordinator.state.phase, .idle)
            XCTAssertTrue(podA.isActivated)
        }
    }

    func test_spareUnreachable_blocksTheSwap() {
        tB.isReachable = false
        XCTAssertEqual(begin(), .failed(.unreachable(.b)))
        XCTAssertEqual(coordinator.state.phase, .idle)
        XCTAssertTrue(podA.isActivated)
    }

    // MARK: interrupted swaps

    func test_releaseReplyLost_podIsReleased_butTheAppDoesNotKnow_retryIsIdempotent() {
        tA.fault = .dropResponse
        XCTAssertEqual(begin(), .failed(.ambiguous(.a)))
        XCTAssertFalse(podA.isActivated, "the pod did release")
        XCTAssertEqual(coordinator.state.phase, .oldPodUnconfirmed)
        XCTAssertEqual(coordinator.state.oldPodSafety, .unknown)
        XCTAssertEqual(coordinator.state.active, .a, "the app must still assume A may be delivering")
        physicallySwap()
        // while unknown, resume re-sends the release; it never activates B
        XCTAssertFalse(podB.isActivated)
        XCTAssertEqual(resume(), .ok)
        XCTAssertEqual(coordinator.state.oldPodSafety, .releasedConfirmed)
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_releaseRequestLost_oldPodStillDelivers_newPodIsNotActivated() {
        tA.fault = .dropRequest
        XCTAssertEqual(begin(), .failed(.ambiguous(.a)))
        XCTAssertTrue(podA.isActivated, "A never saw the release")
        XCTAssertEqual(coordinator.state.phase, .oldPodUnconfirmed)
        physicallySwap()   // even with B docked: no activation without a confirmed release / removal
        XCTAssertEqual(podB.isDocked, true)
        XCTAssertFalse(podB.isActivated)
        // the retry reaches the pod now
        XCTAssertEqual(resume(), .ok)
        XCTAssertFalse(podA.isActivated)
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_oldPodUnreachable_needsUserConfirmationOfPhysicalRemoval() {
        tA.isReachable = false
        XCTAssertEqual(begin(), .failed(.unreachable(.a)))
        XCTAssertEqual(coordinator.state.phase, .oldPodUnconfirmed)
        XCTAssertEqual(coordinator.state.possiblyDelivering, [.a], "A is assumed to be delivering")
        XCTAssertTrue(podA.isActivated && podA.isDocked, "in reality A still delivers")

        // retrying does not help while A is out of reach; B is never activated
        XCTAssertEqual(resume(), .failed(.unreachable(.a)))
        XCTAssertFalse(podB.isActivated)

        // the user takes pod A off the cannula and confirms it
        podA.setDocked(false)
        XCTAssertEqual(outcome(coordinator.confirmOldPodRemoved()), .ok)
        XCTAssertEqual(coordinator.state.oldPodSafety, .userConfirmedRemoved)
        XCTAssertNil(coordinator.state.active)
        podB.setDocked(true)
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
        XCTAssertTrue(podA.isActivated, "A never heard of the release ...")
        let level = podA.reservoirUnits
        podA.advance(by: 3600)
        XCTAssertEqual(podA.reservoirUnits, level, "... but it is undocked, so it cannot deliver")
        assertSingleDeliverer()
    }

    func test_confirmingRemovalIsOnlyPossibleWhileTheOldPodIsUnconfirmed() {
        guard case .failed(.notAllowed) = outcome(coordinator.confirmOldPodRemoved()) else { return XCTFail("idle") }
        XCTAssertEqual(begin(), .ok)
        guard case .failed(.notAllowed) = outcome(coordinator.confirmOldPodRemoved()) else { return XCTFail("already released") }
    }

    func test_activationIsRefusedWhileTheOldPodIsUnknown_evenIfForced() {
        // hand-built state: awaitingDock but without any evidence about A
        var state = coordinator.state
        state.phase = .awaitingDock; state.oldRole = .a; state.newRole = .b; state.oldPodSafety = .unknown
        try? rebuildCoordinator(state: state)
        physicallySwap()
        guard case .failed(.notAllowed) = resume() else { return XCTFail() }
        XCTAssertFalse(podB.isActivated)
    }

    func test_userSaysRemovedButOldPodIsStillOnTheBody_isDetectedAndReleasedWhenItReappears() {
        enforceSingleDeliverer = false
        tA.isReachable = false
        _ = begin()
        XCTAssertEqual(outcome(coordinator.confirmOldPodRemoved()), .ok)     // wrong: A is still docked and active
        podB.setDocked(true)
        finishSwap()
        // the unavoidable window: both pods are active and docked
        XCTAssertEqual(Set(deliveringPods), [.a, .b])

        // A comes back in range and reports itself active: the coordinator releases it at once
        tA.isReachable = true
        var status: PodStatus!
        tA.connect { _ in }
        tA.send(.getStatus) { if case .success(.ok(let s)) = $0 { status = s } }
        coordinator.observe(.a, status: status)
        XCTAssertFalse(podA.isActivated)
        XCTAssertEqual(deliveringPods, [.b])
        XCTAssertTrue(events.contains(.unexpectedActivePod(.a)))
    }

    func test_activateRequestLost_resolvedWithAStatusReadAndAResendWithTheSameActivationID() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        let wrapper = FaultAfterTransport(base: tB, dropRequestOnCommand: .activatePod)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        XCTAssertEqual(resume(), .failed(.ambiguous(.b)))
        XCTAssertFalse(podB.isActivated, "the request never arrived")
        XCTAssertEqual(coordinator.state.phase, .activatingNew)
        let id = coordinator.state.activationID
        finishSwap()
        XCTAssertEqual(podB.activationID, id)
        XCTAssertEqual(wrapper.activateCount, 2)
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_activateReplyLost_podIsActive_theNextResumeFindsOutAndDoesNotActivateTwice() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        // let the dock check (GetStatus) through, then lose the reply of the Activate
        let wrapper = FaultAfterTransport(base: tB, dropResponseOnCommand: .activatePod)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        XCTAssertEqual(resume(), .failed(.ambiguous(.b)))
        XCTAssertTrue(podB.isActivated, "the pod did activate")
        XCTAssertEqual(coordinator.state.phase, .activatingNew)
        let id = podB.activationID
        finishSwap()
        XCTAssertEqual(podB.activationID, id, "no second activation")
        XCTAssertEqual(coordinator.state.active, .b)
        XCTAssertEqual(wrapper.activateCount, 1)
    }

    func test_newPodRejectsBecauseItIsNotDocked_stateReturnsToAwaitingDock() {
        XCTAssertEqual(begin(), .ok)
        podA.setDocked(false)
        // B reports docked at the status read, then loses the dock before the Activate arrives
        let wrapper = FaultAfterTransport(base: tB, undockBeforeCommand: .activatePod)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        podB.setDocked(true)
        XCTAssertEqual(resume(), .failed(.rejected(.b, .notDocked)))
        XCTAssertEqual(coordinator.state.phase, .awaitingDock)
        XCTAssertFalse(podB.isActivated)
        podB.setDocked(true)
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_primeReplyLost_userDecides_noBlindRetry() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        let wrapper = FaultAfterTransport(base: tB, dropResponseOnCommand: .prime)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        XCTAssertEqual(resume(), .failed(.ambiguous(.b)))
        XCTAssertEqual(coordinator.state.phase, .primeUncertain)
        XCTAssertEqual(wrapper.primeCount, 1)
        guard case .failed(.notAllowed) = resume() else { return XCTFail("must not retry blindly") }
        XCTAssertEqual(wrapper.primeCount, 1)
        XCTAssertEqual(outcome(coordinator.skipPrime()), .ok)
        finishSwap()
        XCTAssertEqual(wrapper.primeCount, 1)
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_retryPrimeIsPossibleOnPurpose() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        let wrapper = FaultAfterTransport(base: tB, dropResponseOnCommand: .prime)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        _ = resume()
        XCTAssertEqual(coordinator.state.phase, .primeUncertain)
        // the simulated pod is already priming; wait for it, then the explicit retry is refused by the pod's lifecycle
        podB.advance(by: 41)
        let result = run { self.coordinator.retryPrime(completion: $0) }
        XCTAssertNotEqual(result, .ok)   // a primed pod does not prime again; the user can skip instead
        XCTAssertEqual(outcome(coordinator.skipPrime()), .failed(.notAllowed("no uncertain prime")))
    }

    func test_resumeReplyLost_isConfirmedWithAStatusRead() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        let wrapper = FaultAfterTransport(base: tB, dropResponseOnCommand: .confirmAttached)
        try? rebuildWith(transports: [.a: tA, .b: wrapper])
        coordinator.state = savedLatest
        for _ in 0..<6 where coordinator.state.phase != .idle {
            _ = resume(); podA.advance(by: 15); podB.advance(by: 15)
        }
        XCTAssertEqual(coordinator.state.phase, .idle)
        XCTAssertEqual(coordinator.state.active, .b)
        XCTAssertEqual(podB.phase, .active)
    }

    func test_appRestartMidSwap_continuesFromThePersistedPhase() throws {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        let persisted = try JSONDecoder().decode(PodPairState.self, from: JSONEncoder().encode(savedLatest))
        XCTAssertEqual(persisted.phase, .awaitingDock)
        XCTAssertEqual(persisted.oldPodSafety, .releasedConfirmed)
        try rebuildCoordinator(state: persisted)       // "new process"
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .b)
    }

    func test_everyPhaseIsPersistedBeforeItsCommandGoesOut() {
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        finishSwap()
        let phases = saved.map(\.phase)
        // releasingOld was saved before the release, activatingNew before the activation
        XCTAssertLessThan(phases.firstIndex(of: .releasingOld)!, phases.firstIndex(of: .awaitingDock)!)
        XCTAssertLessThan(phases.firstIndex(of: .activatingNew)!, phases.firstIndex(of: .priming)!)
    }

    func test_swapBack_whenTheNewPodIsUnusable_reactivatesTheOldPodWithoutEverActivatingB() {
        XCTAssertEqual(begin(), .ok)
        XCTAssertEqual(outcome(coordinator.reactivateOldPod()), .ok)
        XCTAssertEqual(coordinator.state.newRole, .a)
        // refill/redock A (it was released, so it goes through the refill cycle like any pod)
        _ = podA.handle(.hello(protocolVersion: 1, time: podA.now, utcOffsetMinutes: 0))
        _ = podA.handle(.confirmFill(pulses: 2000))
        podA.setDocked(true)
        finishSwap()
        XCTAssertEqual(coordinator.state.active, .a)
        XCTAssertFalse(podB.isActivated, "B was never activated")
    }

    func test_reactivateOldIsRefusedWhileTheOldPodIsUnknown() {
        tA.isReachable = false
        _ = begin()
        guard case .failed(.notAllowed) = outcome(coordinator.reactivateOldPod()) else { return XCTFail() }
    }

    func test_runningTempBasalIsHandedOverWithItsRemainingDuration() {
        _ = podA.handle(.setTempBasal(rateTicks: 40, durationMinutes: 120))
        tempBasal = (40, podA.now.addingTimeInterval(120 * 60))
        XCTAssertEqual(begin(), .ok)
        physicallySwap()
        podA.advance(by: 0)
        podB.advance(by: 5 * 60); podA.advance(by: 5 * 60)     // time passes while the user swaps
        finishSwap()
        let temp = podB.status.tempBasal
        XCTAssertEqual(temp?.rateTicks, 40)
        // 120 min minus ~5 min swap minus the prime time, rounded up to 30 min on the wire
        XCTAssertNotNil(temp)
        XCTAssertLessThanOrEqual(Int(temp?.remainingMinutes ?? 0), 120)
        XCTAssertGreaterThanOrEqual(Int(temp?.remainingMinutes ?? 0), 90)
    }

    // MARK: alerts

    func test_wearAlerts() {
        var state = coordinator.state
        state.update(.a) { $0.wearSeconds = UInt32(43 * 3600) }
        XCTAssertFalse(PairAlertPolicy().evaluate(state, now: t0).contains { if case .wearWarning = $0 { return true }; return false })
        state.update(.a) { $0.wearSeconds = UInt32(44 * 3600) }
        XCTAssertTrue(PairAlertPolicy().evaluate(state, now: t0).contains(.wearWarning(role: .a, remaining: 8 * 3600)))
        state.update(.a) { $0.wearSeconds = UInt32(52 * 3600) }
        XCTAssertTrue(PairAlertPolicy().evaluate(state, now: t0).contains(.wearExpired(role: .a)))
    }

    func test_spareNotReadyAlert_ofNotChargedNotFilledAndStale() {
        var state = coordinator.state
        state.update(.a) { $0.wearSeconds = UInt32(37 * 3600) }
        state.update(.b) { $0.batteryFraction = 0.2; $0.reservoirUnits = 10; $0.lastSeen = t0.addingTimeInterval(-48 * 3600) }
        let alerts = PairAlertPolicy().evaluate(state, now: t0)
        guard case .spareNotReady(.b, let reasons)? = alerts.first(where: { if case .spareNotReady = $0 { return true }; return false }) else { return XCTFail("\(alerts)") }
        XCTAssertTrue(reasons.contains(.notSeenRecently))
        XCTAssertTrue(reasons.contains { if case .notCharged = $0 { return true }; return false })
        XCTAssertTrue(reasons.contains { if case .notFilled = $0 { return true }; return false })
    }

    func test_spareAlertStaysQuietEarlyInTheWearPeriod_andWhenTheSpareIsReady() {
        var state = coordinator.state
        state.update(.a) { $0.wearSeconds = UInt32(10 * 3600) }
        state.update(.b) { $0.batteryFraction = 0.1; $0.reservoirUnits = 5 }
        XCTAssertTrue(PairAlertPolicy().evaluate(state, now: t0).isEmpty)
        state.update(.a) { $0.wearSeconds = UInt32(40 * 3600) }
        state.update(.b) { $0.batteryFraction = 0.9; $0.reservoirUnits = 100; $0.lastSeen = t0 }
        XCTAssertTrue(PairAlertPolicy().evaluate(state, now: t0).isEmpty)
    }

    // MARK: test plumbing for per-command faults

    private var savedLatest: PodPairState { saved.last ?? coordinator.state }

    private func rebuildWith(transports: [PodRole: OpenPatchTransport]) throws {
        let state = coordinator.state
        coordinator = PairSwapCoordinator(state: state, transports: transports, clock: { [unowned self] in clock },
                                          context: { [unowned self] in SwapContext(program: program, tempBasal: tempBasal) })
        coordinator.stateHandler = { [unowned self] in saved.append($0) }
        coordinator.eventHandler = { [unowned self] in events.append($0) }
    }
}

/// Wraps a transport and injects a fault for ONE specific command kind (the plain `fault` of `SimulatedTransport`
/// hits whatever command is sent next).
private final class FaultAfterTransport: OpenPatchTransport {
    let base: SimulatedTransport
    var dropResponseOnCommand: CommandKind?
    var undockBeforeCommand: CommandKind?
    var dropRequestOnCommand: CommandKind?
    private(set) var activateCount = 0
    private(set) var primeCount = 0
    private var fired = false

    init(base: SimulatedTransport, dropResponseOnCommand: CommandKind? = nil, undockBeforeCommand: CommandKind? = nil,
         dropRequestOnCommand: CommandKind? = nil) {
        self.dropRequestOnCommand = dropRequestOnCommand
        self.base = base; self.dropResponseOnCommand = dropResponseOnCommand; self.undockBeforeCommand = undockBeforeCommand
    }

    var isConnected: Bool { base.isConnected }
    var eventHandler: ((PodEvent) -> Void)? { get { base.eventHandler } set { base.eventHandler = newValue } }
    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { base.connect(completion: completion) }
    func disconnect() { base.disconnect() }

    func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {
        if command.kind == .activatePod { activateCount += 1 }
        if command.kind == .prime { primeCount += 1 }
        if !fired, command.kind == undockBeforeCommand { fired = true; base.pod.setDocked(false) }
        if !fired, command.kind == dropRequestOnCommand {
            fired = true
            base.fault = .dropRequest
        }
        if !fired, command.kind == dropResponseOnCommand {
            fired = true
            base.fault = .dropResponse
        }
        base.send(command, completion: completion)
    }
}
