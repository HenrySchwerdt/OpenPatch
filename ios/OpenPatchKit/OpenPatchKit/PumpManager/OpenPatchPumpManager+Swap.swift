import Foundation
import LoopKit
import OpenPatchCore

/// Two-pod system (spec/design-parameters.md §1b): OpenPatchKit manages the pair A/B as ONE pump.
/// Trio sees one pump whose status comes from the active pod; the other pod is the spare.
///
/// - Pairing: `pair(...)` pairs the first pod (A), `pairSparePod(...)` the second (B). Both get the same pair ID.
/// - Swap: `beginSwap` -> (user removes the old pod / docks the new one) -> `continueSwap` ->
///   `finishSwap` (UI helpers in OpenPatchKitUI). All safety rules live in `PairSwapCoordinator` (OpenPatchCore).
/// - Separate state per pod: `state.pair.pods[...]` (reservoir, battery, wear, dock, calibration, wire sequence).
extension OpenPatchPumpManager {
    // MARK: Setup

    /// The per-pod transport for `role` (the active pod's is `transport`).
    func makePairTransport(for role: PodRole) -> OpenPatchTransport? {
        let st = state
        guard let record = st.pair?.record(role) else { return nil }
        if role == st.podRole { return transport }
        var derived = st
        derived.peripheralIdentifier = record.peripheralIdentifier
        derived.podSize = record.size
        derived.phase = record.phase
        derived.commandSequence = record.commandSequence
        derived.historyCursor = record.historyCursor
        let created = Self.pairTransportFactory(derived, role)
        wire(created, role: role)
        return created
    }

    /// Rebuilds transports and the swap coordinator from the persisted pair state (init and after pairing).
    func configurePair() {
        guard let pair = state.pair else { swapCoordinator = nil; return }
        var transports: [PodRole: OpenPatchTransport] = [:]
        for record in pair.pods {
            if let existing = pairTransports[record.role], record.role != state.podRole {
                transports[record.role] = existing
            } else if let created = makePairTransport(for: record.role) {
                transports[record.role] = created
            }
        }
        if let role = state.podRole { transports[role] = transport; wire(transport, role: role) }
        pairTransports = transports
        let coordinator = PairSwapCoordinator(state: pair, transports: transports, context: { [weak self] in self?.swapContext() })
        coordinator.stateHandler = { [weak self] newState in self?.mutateState { $0.pair = newState } }
        coordinator.eventHandler = { [weak self] event in self?.handle(pairEvent: event) }
        swapCoordinator = coordinator
    }

    func swapContext() -> SwapContext? {
        guard let program = state.basalProgram else { return nil }
        var temp: (rateTicks: UInt16, end: Date)?
        if let dose = state.unfinalizedTempBasal, !dose.isFinished() {
            temp = (UInt16(clamping: UnitConversion.pulses(forUnits: dose.units)), dose.scheduledEnd)
        }
        return SwapContext(program: program, tempBasal: temp)
    }

    /// Registers the first pod (A) in the pair; called by `pair(...)` after the pod answered `hello`.
    func registerFirstPod(completion: @escaping (Error?) -> Void) {
        let size = state.podSize
        let pairID: UInt32 = state.pair?.pairID ?? UInt32.random(in: 1...UInt32.max)
        mutateState { st in
            if st.pair == nil {
                st.pair = PodPairState(pairID: pairID, pods: [PodRecord(role: .a, size: size, peripheralIdentifier: st.peripheralIdentifier, name: st.podName)])
            } else if st.pair?.record(.a) == nil {
                st.pair?.pods.append(PodRecord(role: .a, size: size, peripheralIdentifier: st.peripheralIdentifier, name: st.podName))
            }
            st.podRole = .a
        }
        send(.setPairing(pairID: pairID, role: .a)) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                self.configurePair()
                completion(nil)
            case .failure(let failure): completion(failure.error)
            }
        }
    }

    /// Pairs the second pod (B). The first pod must be paired already (it created the pair ID).
    public func pairSparePod(peripheralIdentifier: UUID?, name: String?, simulated: Bool, size: PodSize? = nil,
                             completion: @escaping (Error?) -> Void) {
        guard let pair = state.pair, state.podRole != nil else { return completion(OpenPatchError.notConfigured) }
        let role = (state.podRole ?? .a).other
        let podSize = size ?? state.podSize
        var record = PodRecord(role: role, size: podSize, peripheralIdentifier: peripheralIdentifier, name: name)
        record.phase = .unpaired
        mutateState { st in
            st.pair?.pods.removeAll { $0.role == role }
            st.pair?.pods.append(record)
        }
        var derived = state
        derived.peripheralIdentifier = peripheralIdentifier
        derived.podSize = podSize
        derived.usesSimulatedPod = simulated
        derived.commandSequence = 1; derived.historyCursor = nil; derived.phase = .unpaired
        let spare = Self.pairTransportFactory(derived, role)
        wire(spare, role: role)
        pairTransports[role] = spare
        let offset = Int16(clamping: state.timeZone.secondsFromGMT() / 60)
        let hello = Command.hello(protocolVersion: PumpConstants.protocolVersion, time: Date(), utcOffsetMinutes: offset)
        sparePodExchange(role, hello) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error): completion(error)
            case .success:
                self.sparePodExchange(role, .setPairing(pairID: pair.pairID, role: role)) { second in
                    if case .failure(let error) = second { return completion(error) }
                    self.configurePair()
                    completion(nil)
                }
            }
        }
    }

    /// One command to a pod that is NOT the active one; the answer only updates that pod's record.
    func sparePodExchange(_ role: PodRole, _ command: Command, completion: @escaping (Result<PodStatus, Error>) -> Void) {
        guard let spare = pairTransports[role] else { return completion(.failure(OpenPatchError.notConfigured)) }
        let go = { [weak self] in
            spare.send(command) { result in
                guard let self else { return }
                switch result {
                case .success(.ok(let status)):
                    if let calibrationProblem = CalibrationProblem.check(status.driveCalibration) {
                        self.mutateState { $0.pair?.update(role) { $0.update(from: status, at: Date()) } }
                        return completion(.failure(OpenPatchError.calibration(calibrationProblem)))
                    }
                    self.mutateState { $0.pair?.update(role) { $0.update(from: status, at: Date()) } }
                    completion(.success(status))
                case .success(.rejected(let reason)): completion(.failure(OpenPatchError.rejected(reason)))
                case .failure(let error): completion(.failure(OpenPatchError.transport(error)))
                }
            }
        }
        if spare.isConnected { go() } else {
            spare.connect { result in
                if case .failure(let error) = result { completion(.failure(OpenPatchError.transport(error))) } else { go() }
            }
        }
    }

    /// Refill cycle of the SPARE pod (it sits on the charger): hello -> fill. Priming happens at the swap, after docking.
    public func fillSparePod(units: Double, completion: @escaping (Error?) -> Void) {
        guard let role = state.pair?.spare ?? state.podRole?.other else { return completion(OpenPatchError.notConfigured) }
        let size = state.pair?.record(role)?.size ?? state.podSize
        do { try size.validateFill(units: units) } catch { return completion(OpenPatchError.fill(error as? FillError ?? .tooSmall(minimum: PodSize.minimumFillUnits))) }
        let offset = Int16(clamping: state.timeZone.secondsFromGMT() / 60)
        let phase = state.pair?.record(role)?.phase ?? .unpaired
        let prepare: (@escaping (Result<PodStatus, Error>) -> Void) -> Void = { next in
            if phase == .deactivated || phase == .unpaired || phase == .paired {
                self.sparePodExchange(role, .hello(protocolVersion: PumpConstants.protocolVersion, time: Date(), utcOffsetMinutes: offset), completion: next)
            } else {
                self.sparePodExchange(role, .getStatus, completion: next)
            }
        }
        prepare { [weak self] result in
            guard let self else { return }
            if case .failure(let error) = result { return completion(error) }
            self.sparePodExchange(role, .confirmFill(pulses: UInt16(UnitConversion.pulses(forUnits: units)))) { filled in
                if case .failure(let error) = filled { completion(error) } else { completion(nil) }
            }
        }
    }

    /// Reads the spare pod's status (reservoir, battery, dock) into its record. Failures are expected (it sleeps).
    public func refreshSparePod(completion: @escaping (Error?) -> Void) {
        guard let role = state.pair?.spare ?? state.podRole?.other, !state.isSwapping else { return completion(nil) }
        sparePodExchange(role, .getStatus) { [weak self] result in
            self?.evaluatePairAlerts()
            if case .failure(let error) = result { completion(error) } else { completion(nil) }
        }
    }

    func refreshSparePodIfStale(maxAge: TimeInterval = 30 * 60) {
        guard let pair = state.pair, let spare = pair.spare, pairTransports[spare] != nil else { return }
        if let seen = pair.record(spare)?.lastSeen, Date().timeIntervalSince(seen) < maxAge { return }
        refreshSparePod { _ in }
    }

    // MARK: Swap

    /// Starts the swap to the spare pod. The spare is checked first (reachable, calibration, charged, filled); if it is not
    /// fit, nothing happens to the active pod.
    public func beginSwap(completion: @escaping (Error?) -> Void) {
        guard let coordinator = swapCoordinator else { return completion(OpenPatchError.notConfigured) }
        guard state.phase == .active || state.phase == .suspended else { return completion(OpenPatchError.notReady(state.phase)) }
        coordinator.begin { [weak self] result in self?.finishSwapStep(result, completion) }
    }

    /// Continues after an interruption, a user action (pod docked) or an app restart.
    public func continueSwap(completion: @escaping (Error?) -> Void) {
        guard let coordinator = swapCoordinator else { return completion(OpenPatchError.notConfigured) }
        coordinator.resume { [weak self] result in self?.finishSwapStep(result, completion) }
    }

    /// The old pod could not be reached and the user states that it is physically removed from the cannula.
    public func confirmOldPodPhysicallyRemoved() -> Error? {
        guard let coordinator = swapCoordinator else { return OpenPatchError.notConfigured }
        if case .failure(let failure) = coordinator.confirmOldPodRemoved() { return OpenPatchError.swap(failure) }
        releaseOldPodLocally()
        return nil
    }

    public func retryUncertainPrime(completion: @escaping (Error?) -> Void) {
        guard let coordinator = swapCoordinator else { return completion(OpenPatchError.notConfigured) }
        coordinator.retryPrime { [weak self] result in self?.finishSwapStep(result, completion) }
    }

    public func skipUncertainPrime() -> Error? {
        guard let coordinator = swapCoordinator else { return OpenPatchError.notConfigured }
        if case .failure(let failure) = coordinator.skipPrime() { return OpenPatchError.swap(failure) }
        return nil
    }

    /// Cancels a swap that cannot be finished by taking the previous pod back (only possible while the new pod was never activated).
    public func reactivateOldPod() -> Error? {
        guard let coordinator = swapCoordinator else { return OpenPatchError.notConfigured }
        if case .failure(let failure) = coordinator.reactivateOldPod() { return OpenPatchError.swap(failure) }
        return nil
    }

    private func finishSwapStep(_ result: Result<Void, SwapFailure>, _ completion: @escaping (Error?) -> Void) {
        if case .failure(let failure) = result { return completion(OpenPatchError.swap(failure)) }
        completion(nil)
    }

    // MARK: Coordinator events -> Trio-facing state

    func handle(pairEvent event: PairEvent) {
        switch event {
        case .phaseChanged(let phase):
            switch phase {
            case .awaitingDock: releaseOldPodLocally()
            case .oldPodUnconfirmed:
                issue(.swapOldPodUnconfirmed, body: NSLocalizedString("The old pod did not confirm that it stopped. Confirm that it is physically removed or try again. The new pod will not start until then.", bundle: .openPatchKit, comment: "Alert body"))
            default: break
            }
        case .swapCompleted(let role): adoptActivePod(role)
        case .unexpectedActivePod(let role):
            issue(.podConflict, body: String(format: NSLocalizedString("Pod %@ reported that it was active although it must not be. It was told to stop.", bundle: .openPatchKit, comment: "Alert body"), role.label))
        }
    }

    /// The old pod stopped (confirmed or removed): close its doses and leave "no pod delivers" in the host-facing state.
    func releaseOldPodLocally() {
        let now = Date()
        guard state.phase == .active || state.phase == .suspended else { return }
        if let bolus = state.unfinalizedBolus { finalize(bolus: bolus.cancelled(at: now)) }
        finalizeRunningTempBasal(cancelAt: now)
        mutateState { $0.phase = .deactivated; $0.suspendedAt = nil; $0.podReportsActive = false }
        reportDoses(extra: [.openPatchSuspend(at: now)])
    }

    /// The new pod runs: it becomes the pod `transport` talks to, and Trio's status follows it.
    func adoptActivePod(_ role: PodRole) {
        guard let new = pairTransports[role] else { return }
        let now = Date()
        mutateState { st in
            st.podRole = role
            if let record = st.pair?.record(role) {
                st.peripheralIdentifier = record.peripheralIdentifier
                st.podName = record.name
                st.podSize = record.size
                st.commandSequence = record.commandSequence
                st.historyCursor = record.historyCursor
                st.reservoirUnits = record.reservoirUnits
                st.batteryFraction = record.batteryFraction
                st.driveCalibration = record.calibration
                st.calibrationProblem = CalibrationProblem.check(record.calibration)
            }
            st.phase = .active
            st.faultCode = nil
            st.activatedAt = now; st.resumedAt = now; st.suspendedAt = nil
            st.podReportsActive = true
            st.isSetupCompleted = true
        }
        // Each pod keeps its own transport (and wire sequence); only the pointer Trio-facing code uses moves.
        adoptTempBasalFromNextStatus = true   // the swap may have handed a running temp basal to this pod
        transport = new
        wire(new, role: role)
        reportDoses(extra: [.openPatchResume(at: now, insulinType: state.insulinType)])
        send(.getStatus) { _ in }
    }

    func handleSparePodEvent(_ event: PodEvent, from role: PodRole) {
        switch event {
        case .released(_, let reason):
            log("pod \(role.label) released (\(reason))")
        case .docked(let docked):
            mutateState { $0.pair?.update(role) { $0.isDocked = docked } }
        default:
            log("event from pod \(role.label): \(event)")
        }
    }

    // MARK: Alerts

    /// Wear time of the active pod and readiness of the spare. Each condition is raised once until it clears.
    func evaluatePairAlerts() {
        guard let coordinator = swapCoordinator else { return }
        if let current = state.pair { coordinator.sync(current) }
        let current = coordinator.alerts()
        var keys = Set<String>()
        for alert in current {
            switch alert {
            case .wearWarning(let role, let remaining):
                keys.insert("wearWarning")
                guard raisedPairAlerts.insert("wearWarning").inserted else { continue }
                issue(.podWearWarning, body: String(format: NSLocalizedString("Pod %@ has been worn for 44 hours or more. Swap to the other pod within %.0f hours.", bundle: .openPatchKit, comment: "Alert body"), role.label, remaining / 3600))
            case .wearExpired(let role):
                keys.insert("wearExpired")
                guard raisedPairAlerts.insert("wearExpired").inserted else { continue }
                issue(.podWearExpired, body: String(format: NSLocalizedString("Pod %@ reached its maximum wear time and stopped delivering insulin. Swap pods now.", bundle: .openPatchKit, comment: "Alert body"), role.label))
            case .spareNotReady(let role, let reasons):
                keys.insert("spare")
                guard raisedPairAlerts.insert("spare").inserted else { continue }
                issue(.spareNotReady, body: String(format: NSLocalizedString("Spare pod %@ is not ready: %@", bundle: .openPatchKit, comment: "Alert body"), role.label, Self.describe(reasons)))
            }
        }
        raisedPairAlerts = raisedPairAlerts.intersection(keys)
    }

    static func describe(_ problems: [SpareProblem]) -> String {
        problems.map { problem -> String in
            switch problem {
            case .notCharged(let fraction): return String(format: NSLocalizedString("battery at %d %% - put it on the charger", bundle: .openPatchKit, comment: "Spare problem"), Int(fraction * 100))
            case .notFilled(let units, let needed): return String(format: NSLocalizedString("only %.0f U inside, fill at least %.0f U", bundle: .openPatchKit, comment: "Spare problem"), units, needed)
            case .notSeenRecently: return NSLocalizedString("not seen recently - wake it with its button", bundle: .openPatchKit, comment: "Spare problem")
            case .unknown: return NSLocalizedString("not checked yet", bundle: .openPatchKit, comment: "Spare problem")
            }
        }.joined(separator: "; ")
    }

    // MARK: Delivery gate

    /// Setup / fill / prime: a swap must not be running and the calibration must be known (the pod is not active yet).
    func setupBlock(_ st: OpenPatchPumpManagerState) -> OpenPatchError? {
        if st.isSwapping { return .swapInProgress }
        return st.calibrationBlock
    }

    /// Everything that must stop priming, filling and delivery (swap running, no valid calibration, pod not the active one).
    func deliveryBlock(_ st: OpenPatchPumpManagerState) -> OpenPatchError? {
        if st.isSwapping { return .swapInProgress }
        if let block = st.calibrationBlock { return block }
        if st.podReportsActive == false { return .notActivePod }
        return nil
    }
}
