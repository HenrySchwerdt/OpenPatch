import Foundation

/// What the swap needs from the pump manager at activation time.
public struct SwapContext {
    public var program: BasalProgram
    /// Temp basal currently running on the old pod: rate and absolute end. Handed to the new pod with the remaining duration.
    public var tempBasal: (rateTicks: UInt16, end: Date)?
    public init(program: BasalProgram, tempBasal: (rateTicks: UInt16, end: Date)? = nil) {
        self.program = program; self.tempBasal = tempBasal
    }
}

public enum SwapFailure: Error, Equatable {
    case unreachable(PodRole)               // could not connect; nothing was sent
    case ambiguous(PodRole)                 // sent, reply lost: the pod may have executed it
    case rejected(PodRole, NackReason)
    case calibration(PodRole, CalibrationProblem)
    case notDocked(PodRole)
    case spareNotReady([SpareProblem])
    case notAllowed(String)
}

public enum PairEvent: Equatable {
    case phaseChanged(SwapPhase)
    case swapCompleted(newActive: PodRole)
    /// A pod that must not deliver reported itself active; the coordinator sent it `Release`.
    case unexpectedActivePod(PodRole)
}

/// State machine of the A/B pod swap. SAFETY RULES (each one is covered by tests):
///  1. Never two active pods: `Activate(new)` is only sent once the old pod is `releasedConfirmed` or the user has
///     confirmed it was physically removed (an undocked pod cannot deliver). Unknown = no activation.
///  2. The new pod is checked (reachable, docked, drive calibration known, filled) BEFORE the old pod is released.
///  3. Every step that can leave the outcome unknown is persisted first and is idempotent or resolved with a status read:
///     Release (idempotent on the pod), Activate (same activation ID), Resume (status check).
///  4. Prime after an unknown outcome is never retried blindly.
///  5. A pod that reports itself active although it should not is released at once.
public final class PairSwapCoordinator {
    public internal(set) var state: PodPairState
    public var stateHandler: ((PodPairState) -> Void)?
    public var eventHandler: ((PairEvent) -> Void)?

    private let transports: [PodRole: OpenPatchTransport]
    private let context: () -> SwapContext?
    private let clock: () -> Date
    public var policy: PairAlertPolicy

    public init(state: PodPairState, transports: [PodRole: OpenPatchTransport], policy: PairAlertPolicy = PairAlertPolicy(),
                clock: @escaping () -> Date = Date.init, context: @escaping () -> SwapContext?) {
        self.state = state; self.transports = transports; self.policy = policy; self.clock = clock; self.context = context
    }

    // MARK: Public API

    /// Starts a swap to the spare pod. Fails without touching the old pod if the spare cannot take over.
    public func begin(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard state.phase == .idle else { return completion(.failure(.notAllowed("swap already in progress"))) }
        guard let old = state.active else { return completion(.failure(.notAllowed("no active pod"))) }
        guard let ctx = context() else { return completion(.failure(.notAllowed("no basal program"))) }
        let new = old.other
        exec(new, .getStatus) { [self] result in
            switch result {
            case .failure(let failure): completion(.failure(failure))
            case .success(let status):
                if let problem = CalibrationProblem.check(status.driveCalibration) { return completion(.failure(.calibration(new, problem))) }
                let problems = policy.spareProblems(state.record(new) ?? PodRecord(role: new, size: .u100), now: clock())
                guard problems.isEmpty else { return completion(.failure(.spareNotReady(problems))) }
                guard status.pairing?.isActive == false else { return completion(.failure(.notAllowed("spare pod is already active"))) }
                state.oldRole = old; state.newRole = new
                state.activationID = state.nextActivationID
                state.nextActivationID = state.nextActivationID &+ 1 == 0 ? 1 : state.nextActivationID &+ 1
                state.oldPodSafety = .unknown
                state.tempBasalRate = ctx.tempBasal?.rateTicks
                state.tempBasalEnd = ctx.tempBasal?.end
                state.lastError = nil
                setPhase(.releasingOld)       // persisted BEFORE the release goes out
                performRelease(completion: completion)
            }
        }
    }

    /// Continues whatever phase the swap is in (after a BLE loss, an app restart, or a user action).
    public func resume(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        switch state.phase {
        case .idle: completion(.success(()))
        case .releasingOld, .oldPodUnconfirmed: performRelease(completion: completion)
        case .awaitingDock: checkDockAndActivate(completion: completion)
        case .activatingNew: resolveActivation(completion: completion)
        case .priming: performPrime(completion: completion)
        case .primeUncertain: completion(.failure(.notAllowed("prime outcome unknown: retry the prime or skip it")))
        case .resuming: performResume(completion: completion)
        }
    }

    /// The old pod cannot be reached. The user states it is physically off the cannula. Because an undocked pod cannot
    /// deliver (hardware gate), this is accepted as proof that the old pod is no longer delivering.
    public func confirmOldPodRemoved() -> Result<Void, SwapFailure> {
        guard state.phase == .releasingOld || state.phase == .oldPodUnconfirmed else {
            return .failure(.notAllowed("no unconfirmed old pod"))
        }
        state.oldPodSafety = .userConfirmedRemoved
        if state.active == state.oldRole { state.active = nil }
        if let old = state.oldRole { state.update(old) { $0.isDocked = false; $0.reportedActive = false } }
        setPhase(.awaitingDock)
        return .success(())
    }

    /// After an unknown prime outcome: prime again (a little more insulin in the connector).
    public func retryPrime(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard state.phase == .primeUncertain else { return completion(.failure(.notAllowed("no uncertain prime"))) }
        setPhase(.priming)
        performPrime(completion: completion)
    }

    /// After an unknown prime outcome: assume it happened.
    public func skipPrime() -> Result<Void, SwapFailure> {
        guard state.phase == .primeUncertain else { return .failure(.notAllowed("no uncertain prime")) }
        setPhase(.resuming)
        return .success(())
    }

    /// Swaps back to the pod that was just released (the new pod cannot be used). Only before `Activate` was ever sent.
    public func reactivateOldPod() -> Result<Void, SwapFailure> {
        guard state.phase == .awaitingDock || state.phase == .oldPodUnconfirmed, let old = state.oldRole,
              state.oldPodSafety != .unknown else { return .failure(.notAllowed("old pod not confirmed released")) }
        state.newRole = old
        state.oldRole = old.other
        state.oldPodSafety = .releasedConfirmed   // the other pod was never activated
        state.activationID = state.nextActivationID
        state.nextActivationID = state.nextActivationID &+ 1 == 0 ? 1 : state.nextActivationID &+ 1
        setPhase(.awaitingDock)
        return .success(())
    }

    /// Feed every status read (any pod) through here. Updates the pod's record and releases a pod that is active
    /// although it must not deliver (e.g. the user said "removed" but the old pod is in fact still on the body).
    public func observe(_ role: PodRole, status: PodStatus, completion: (() -> Void)? = nil) {
        state.update(role) { $0.update(from: status, at: clock()) }
        defer { save() }
        guard status.pairing?.isActive == true, !isExpectedActive(role) else { completion?(); return }
        eventHandler?(.unexpectedActivePod(role))
        exec(role, .releasePod(pairID: state.pairID)) { [weak self] _ in
            self?.state.update(role) { $0.reportedActive = false }
            self?.save()
            completion?()
        }
    }

    /// Adopts the persisted pair state (e.g. records refreshed by the pump manager) without touching a swap in flight.
    public func sync(_ newState: PodPairState) { state = newState }

    public func alerts() -> [PairAlert] { policy.evaluate(state, now: clock()) }

    // MARK: Steps

    private func performRelease(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard let old = state.oldRole else { return completion(.failure(.notAllowed("no old pod"))) }
        exec(old, .releasePod(pairID: state.pairID)) { [self] result in
            switch result {
            case .success(let status):
                state.oldPodSafety = .releasedConfirmed
                state.lastRelease = status.releaseReport
                if state.active == old { state.active = nil }
                state.update(old) { $0.reportedActive = false }
                state.lastError = nil
                setPhase(.awaitingDock)
                completion(.success(()))
            case .failure(let failure):
                state.lastError = "\(failure)"
                setPhase(.oldPodUnconfirmed)
                completion(.failure(failure))
            }
        }
    }

    private func checkDockAndActivate(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard let new = state.newRole else { return completion(.failure(.notAllowed("no new pod"))) }
        guard state.oldPodSafety != .unknown else { return completion(.failure(.notAllowed("old pod not confirmed released or removed"))) }
        exec(new, .getStatus) { [self] result in
            switch result {
            case .failure(let failure): completion(.failure(failure))
            case .success(let status):
                if let problem = CalibrationProblem.check(status.driveCalibration) { return completion(.failure(.calibration(new, problem))) }
                guard let pairing = status.pairing, pairing.pairID == state.pairID else { return completion(.failure(.rejected(new, .pairMismatch))) }
                guard pairing.isDocked else { return completion(.failure(.notDocked(new))) }
                if pairing.isActive { return afterActivation(new, completion: completion) }   // activated earlier, reply was lost
                guard status.reservoirUnits > PumpConstants.primeUnits else { return completion(.failure(.rejected(new, .insufficientReservoir))) }
                activate(new, completion: completion)
            }
        }
    }

    private func activate(_ new: PodRole, completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard state.oldPodSafety != .unknown else { return completion(.failure(.notAllowed("old pod not confirmed released or removed"))) }
        guard let ctx = context() else { return completion(.failure(.notAllowed("no basal program"))) }
        var handover: HandoverTempBasal?
        if let rate = state.tempBasalRate, let end = state.tempBasalEnd {
            let minutes = Int((max(end.timeIntervalSince(clock()), 0) / 60).rounded(.up))
            if minutes > 0 { handover = HandoverTempBasal(rateTicks: rate, remainingMinutes: UInt16(clamping: minutes)) }
        }
        setPhase(.activatingNew)               // persisted BEFORE the Activate goes out
        exec(new, .activatePod(pairID: state.pairID, activationID: state.activationID, program: ctx.program, tempBasal: handover)) { [self] result in
            switch result {
            case .success: afterActivation(new, completion: completion)
            case .failure(.unreachable(let role)):
                setPhase(.awaitingDock)       // never left the phone: the pod is not active
                completion(.failure(.unreachable(role)))
            case .failure(.rejected(let role, let reason)):
                state.lastError = "\(reason)"
                setPhase(.awaitingDock)       // definitive refusal: not active
                completion(.failure(.rejected(role, reason)))
            case .failure(let failure):
                completion(.failure(failure))  // ambiguous: stays `.activatingNew`, resolved by a status read
            }
        }
    }

    private func resolveActivation(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard let new = state.newRole else { return completion(.failure(.notAllowed("no new pod"))) }
        exec(new, .getStatus) { [self] result in
            switch result {
            case .failure(let failure): completion(.failure(failure))
            case .success(let status):
                if status.pairing?.isActive == true { afterActivation(new, completion: completion) }
                else { activate(new, completion: completion) }   // same activation ID: idempotent on the pod
            }
        }
    }

    private func afterActivation(_ new: PodRole, completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        state.active = new
        state.lastError = nil
        setPhase(.priming)
        performPrime(completion: completion)
    }

    private func performPrime(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard let new = state.newRole else { return completion(.failure(.notAllowed("no new pod"))) }
        exec(new, .prime) { [self] result in
            switch result {
            case .success:
                setPhase(.resuming)
                performResume(completion: completion)
            case .failure(.ambiguous(let role)):
                setPhase(.primeUncertain)
                completion(.failure(.ambiguous(role)))
            case .failure(let failure):
                completion(.failure(failure))
            }
        }
    }

    private func performResume(completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        guard let new = state.newRole else { return completion(.failure(.notAllowed("no new pod"))) }
        exec(new, .confirmAttached) { [self] result in
            switch result {
            case .success: finish(new, completion: completion)
            case .failure(.rejected(_, .invalidState)):
                // a retried Resume on a pod that already runs: confirm with a status read
                exec(new, .getStatus) { [self] again in
                    if case .success(let status) = again, status.phase == .active, status.pairing?.isActive == true {
                        finish(new, completion: completion)
                    } else {
                        completion(.failure(.rejected(new, .invalidState)))
                    }
                }
            case .failure(let failure): completion(.failure(failure))
            }
        }
    }

    private func finish(_ new: PodRole, completion: @escaping (Result<Void, SwapFailure>) -> Void) {
        state.active = new
        state.phase = .idle
        state.oldRole = nil; state.newRole = nil
        state.tempBasalRate = nil; state.tempBasalEnd = nil
        state.lastError = nil
        save()
        eventHandler?(.phaseChanged(.idle))
        eventHandler?(.swapCompleted(newActive: new))
        completion(.success(()))
    }

    // MARK: Plumbing

    private func isExpectedActive(_ role: PodRole) -> Bool {
        if role == state.active { return true }
        guard state.isSwapping else { return false }
        switch state.phase {
        case .activatingNew, .priming, .primeUncertain, .resuming: return role == state.newRole
        case .releasingOld, .oldPodUnconfirmed: return role == state.oldRole   // being released right now
        case .awaitingDock, .idle: return false
        }
    }

    private func setPhase(_ phase: SwapPhase) {
        state.phase = phase
        save()
        eventHandler?(.phaseChanged(phase))
    }

    private func save() { stateHandler?(state) }

    /// Connects if needed, sends one command. `unreachable` = nothing was sent; `ambiguous` = sent, reply lost.
    private func exec(_ role: PodRole, _ command: Command, _ completion: @escaping (Result<PodStatus, SwapFailure>) -> Void) {
        guard let transport = transports[role] else { return completion(.failure(.unreachable(role))) }
        let send = { [weak self] in
            transport.send(command) { result in
                guard let self else { return }
                switch result {
                case .success(.ok(let status)):
                    self.state.update(role) { $0.update(from: status, at: self.clock()) }
                    self.save()
                    completion(.success(status))
                case .success(.rejected(let reason)): completion(.failure(.rejected(role, reason)))
                case .failure(let error):
                    let notSent = error == .notConnected || error == .bluetoothUnavailable
                    completion(.failure(notSent ? .unreachable(role) : .ambiguous(role)))
                }
            }
        }
        if transport.isConnected { send() } else {
            transport.connect { result in
                if case .failure = result { completion(.failure(.unreachable(role))) } else { send() }
            }
        }
    }
}
