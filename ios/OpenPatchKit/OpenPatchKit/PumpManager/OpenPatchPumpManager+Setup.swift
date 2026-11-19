import Foundation
import LoopKit
import OpenPatchCore

/// Pod activation / refill steps driven by the setup UI.
/// Flow: choose size -> pair -> fill with syringe -> prime -> attach to cannula head -> active.
extension OpenPatchPumpManager {
    public func selectPodSize(_ size: PodSize) {
        mutateState { $0.podSize = size }
    }

    /// Pairs with the given peripheral (or the in-memory simulator) and sends `hello`.
    public func pair(peripheralIdentifier: UUID?, name: String?, simulated: Bool, completion: @escaping (Error?) -> Void) {
        mutateState { st in
            st.peripheralIdentifier = peripheralIdentifier
            st.podName = name
            st.usesSimulatedPod = simulated
        }
        replaceTransport(Self.transportFactory(state))
        ensurePairingSecret(on: transport, peripheral: peripheralIdentifier, simulated: simulated) { [weak self] error in
            guard let self else { return }
            if let error { return completion(error) }
            self.helloAfterPairing(peripheral: peripheralIdentifier, simulated: simulated, mayRepair: true, completion: completion)
        }
    }

    private func helloAfterPairing(peripheral: UUID?, simulated: Bool, mayRepair: Bool, completion: @escaping (Error?) -> Void) {
        let offset = Int16(clamping: state.timeZone.secondsFromGMT() / 60)
        send(.hello(protocolVersion: PumpConstants.protocolVersion, time: Date(), utcOffsetMinutes: offset)) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                if let block = self.state.calibrationBlock { return completion(block) }   // refuse a pod with an unknown drive right away
                self.registerFirstPod(completion: completion)
            case .failure(let failure):
                // The pod does not know the stored secret (paired by another phone, or reset): forget it and pair once more. This
                // only works while the pod's button window is open; otherwise the user gets the "press the button" message.
                if mayRepair, case .transport(.notPaired) = failure.error, let key = Self.podKey(for: self.state) {
                    Self.pairingSecretStore.remove(for: key)
                    (self.transport as? V1Transport)?.setPairingSecret(nil)
                    return self.ensurePairingSecret(on: self.transport, peripheral: peripheral, simulated: simulated) { error in
                        if let error { return completion(error) }
                        self.helloAfterPairing(peripheral: peripheral, simulated: simulated, mayRepair: false, completion: completion)
                    }
                }
                completion(failure.error)
            }
        }
    }

    /// Starts a refill on a deactivated reusable pod (hello moves it back to `paired`).
    public func beginRefill(completion: @escaping (Error?) -> Void) {
        let offset = Int16(clamping: state.timeZone.secondsFromGMT() / 60)
        send(.hello(protocolVersion: PumpConstants.protocolVersion, time: Date(), utcOffsetMinutes: offset)) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
        }
    }

    /// LEGACY pods only (C reference firmware): the user injected `units` with a syringe and confirms the amount. A pod that
    /// supports the assisted fill (the cup pod) is filled with `startFill` and refuses this: it cannot take fluid in without
    /// retracting its plunger.
    public func confirmFill(units: Double, completion: @escaping (Error?) -> Void) {
        if let block = setupBlock(state) { return completion(block) }
        guard state.driveCalibration?.allowedFillModes.contains(.manualConfirm) == true else {
            return completion(OpenPatchError.fillModeNotAllowed(.manualConfirm))
        }
        let size = state.podSize
        do { try size.validateFill(units: units) } catch { return completion(OpenPatchError.fill(error as? FillError ?? .tooSmall(minimum: PodSize.minimumFillUnits))) }
        send(.confirmFill(pulses: UInt16(UnitConversion.pulses(forUnits: units)))) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
        }
    }

    /// Starts priming. Completion fires when the command is accepted; `.primed` arrives via pod event / status poll.
    public func startPrime(completion: @escaping (Error?) -> Void) {
        if let block = setupBlock(state) { return completion(block) }
        // The pod only primes (and delivers) as the ACTIVE pod of its pair, and only docked: activate it first.
        guard state.podReportsActive == false else { return sendPrime(completion) }
        guard let program = state.basalProgram, let pair = state.pair else { return completion(OpenPatchError.notConfigured) }
        let activationID = pair.nextActivationID
        mutateState { $0.pair?.nextActivationID = activationID &+ 1 == 0 ? 1 : activationID &+ 1; $0.pair?.activationID = activationID }
        send(.activatePod(pairID: pair.pairID, activationID: activationID, program: program, tempBasal: nil)) { [weak self] result in
            switch result {
            case .failure(let failure): completion(failure.error)
            case .success: self?.sendPrime(completion)
            }
        }
    }

    /// Seconds between the prime attempts while the pod takes up the lost motion of its drive. Tests set 0.
    public static var primeTakeupRetryDelay: TimeInterval = PumpConstants.primeTakeupRetryDelay

    /// After an assisted fill the pod first takes up the lost motion of its drive, no faster than its per-minute delivery cap
    /// allows, over several prime commands: it answers `Hourly` after each slice and the phone repeats the command a minute
    /// later (`PumpConfig::takeup_um`). `state.primeTakeupAttempt` tells the screen which attempt is running.
    private func sendPrime(attempt: Int = 1, _ completion: @escaping (Error?) -> Void) {
        send(.prime) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                self.mutateState { $0.primeTakeupAttempt = nil }
                completion(nil)
            case .failure(let failure):
                if case .rejected(.hourlyLimit) = failure.error, attempt < PumpConstants.primeTakeupMaxAttempts {
                    self.mutateState { $0.primeTakeupAttempt = attempt }
                    self.workQueue.asyncAfter(deadline: .now() + Self.primeTakeupRetryDelay) { [weak self] in
                        self?.sendPrime(attempt: attempt + 1, completion)
                    }
                } else {
                    self.mutateState { $0.primeTakeupAttempt = nil }
                    completion(failure.error)
                }
            }
        }
    }

    /// Polls the pod (used by the prime progress screen when no event arrives, e.g. after a reconnect).
    public func refreshStatus(completion: @escaping (Error?) -> Void) {
        send(.getStatus) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
        }
    }

    /// Pod is on the cannula head: program basal + limits, then start delivery.
    public func activate(completion: @escaping (Error?) -> Void) {
        guard let program = state.basalProgram else { return completion(OpenPatchError.notConfigured) }
        if let block = setupBlock(state) { return completion(block) }
        let limits = state.safetyLimits
        send(.setLimits(limits)) { [weak self] limitResult in
            guard let self else { return }
            if case .failure(let failure) = limitResult { return completion(failure.error) }
            self.send(.setBasalProgram(program)) { [weak self] programResult in
                guard let self else { return }
                if case .failure(let failure) = programResult { return completion(failure.error) }
                self.send(.confirmAttached) { [weak self] result in
                    guard let self else { return }
                    switch result {
                    case .failure(let failure): completion(failure.error)
                    case .success:
                        let now = Date()
                        self.mutateState {
                            $0.isSetupCompleted = true; $0.activatedAt = now; $0.resumedAt = now; $0.suspendedAt = nil
                            if $0.pair?.active == nil { $0.pair?.active = $0.podRole }
                        }
                        self.configurePair()
                        self.reportDoses(extra: [.openPatchResume(at: now, insulinType: self.state.insulinType)])
                        completion(nil)
                    }
                }
            }
        }
    }

    /// Removes the pod from the body (cannula stays). The pod can be refilled and reused.
    public func deactivatePod(completion: @escaping (Error?) -> Void) {
        // Two-pod: the pod is RELEASED (never delivers again until a new Activate); single pods are just suspended.
        let command: Command = state.pair.map { .releasePod(pairID: $0.pairID) } ?? .deactivate
        send(command) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let failure): completion(failure.error)
            case .success:
                let now = Date()
                if let bolus = self.state.unfinalizedBolus { self.finalize(bolus: bolus.cancelled(at: now)) }
                self.finalizeRunningTempBasal(cancelAt: now)
                self.mutateState { $0.phase = .deactivated; $0.suspendedAt = nil }
                self.reportDoses(extra: [.openPatchSuspend(at: now)])
                completion(nil)
            }
        }
    }
}
