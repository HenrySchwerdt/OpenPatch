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
        let offset = Int16(clamping: state.timeZone.secondsFromGMT() / 60)
        send(.hello(protocolVersion: PumpConstants.protocolVersion, time: Date(), utcOffsetMinutes: offset)) { result in
            switch result {
            case .success: completion(nil)
            case .failure(let failure): completion(failure.error)
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

    /// The user injected `units` into the pod with a syringe and confirms the amount.
    public func confirmFill(units: Double, completion: @escaping (Error?) -> Void) {
        let size = state.podSize
        do { try size.validateFill(units: units) } catch { return completion(OpenPatchError.fill(error as? FillError ?? .tooSmall(minimum: PodSize.minimumFillUnits))) }
        send(.confirmFill(pulses: UInt16(UnitConversion.pulses(forUnits: units)))) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
        }
    }

    /// Starts priming. Completion fires when the command is accepted; `.primed` arrives via pod event / status poll.
    public func startPrime(completion: @escaping (Error?) -> Void) {
        send(.prime) { result in
            if case .failure(let failure) = result { completion(failure.error) } else { completion(nil) }
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
                        self.mutateState { $0.isSetupCompleted = true; $0.activatedAt = now; $0.resumedAt = now; $0.suspendedAt = nil }
                        self.reportDoses(extra: [.openPatchResume(at: now, insulinType: self.state.insulinType)])
                        completion(nil)
                    }
                }
            }
        }
    }

    /// Removes the pod from the body (cannula stays). The pod can be refilled and reused.
    public func deactivatePod(completion: @escaping (Error?) -> Void) {
        send(.deactivate) { [weak self] result in
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
