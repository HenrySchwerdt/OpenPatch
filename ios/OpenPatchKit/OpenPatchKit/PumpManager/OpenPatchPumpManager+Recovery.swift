import Foundation
import LoopKit
import OpenPatchCore

/// Uncertain delivery (docs: Loop / Trio contract). When the reply of a delivery command is lost the pod may have executed it.
/// The manager then
///  1. reports `PumpManagerError.uncertainDelivery` and sets `deliveryIsUncertain` in its status,
///  2. remembers WHAT was sent (`PendingCommand`, persisted),
///  3. reads the pod again on its own (`getStatus`, which also reads the history), after a few seconds, then with growing delays,
///  4. decides with the pod's own evidence: a `BolusStart` / `TempStart` event in the history, or the running dose in the status,
///     proves execution; a fully read history without such an event proves the opposite,
///  5. adopts the dose (executed) or forgets the command (not executed) and clears the uncertainty.
/// If the history cannot be read completely the delivery stays uncertain until it can, or until the user clears it.
extension OpenPatchPumpManager {
    /// Delays (seconds) of the automatic recovery reads after a lost reply. Tests set short ones.
    public static var uncertaintyRecoveryDelays: [TimeInterval] = [3, 10, 30, 60, 120, 300]

    func markUncertain(after command: Command) {
        let automatic = lockedInFlightBolusAutomatic()
        let now = Date()
        mutateState { st in
            st.deliveryUncertainSince = st.deliveryUncertainSince ?? now
            guard let new = PendingCommand.make(for: command, automatic: automatic, at: now, historyCursor: st.historyCursor) else { return }
            // A bolus is what must never be forgotten (double dosing): it wins over any other pending command.
            if case .bolus = st.pendingCommand?.kind { return }
            st.pendingCommand = new
        }
        scheduleUncertaintyRecovery()
    }

    func lockedInFlightBolusAutomatic() -> Bool {
        lock.lock(); defer { lock.unlock() }
        return inFlightBolusAutomatic
    }

    func setInFlightBolusAutomatic(_ value: Bool) {
        lock.lock(); inFlightBolusAutomatic = value; lock.unlock()
    }

    /// Reads the pod again, with growing delays, until the uncertainty is resolved.
    func scheduleUncertaintyRecovery(attempt: Int = 0) {
        let delays = Self.uncertaintyRecoveryDelays
        guard attempt < delays.count, state.deliveryUncertainSince != nil else { return clearRecoveryScheduled() }
        lock.lock()
        if attempt == 0, recoveryScheduled { lock.unlock(); return }
        recoveryScheduled = true
        lock.unlock()
        workQueue.asyncAfter(deadline: .now() + delays[attempt]) { [weak self] in
            guard let self else { return }
            guard self.state.deliveryUncertainSince != nil, !self.state.isSwapping else { return self.clearRecoveryScheduled() }
            self.send(.getStatus) { [weak self] result in
                guard let self else { return }
                if case .failure(let failure) = result { self.log("uncertainty recovery read \(attempt + 1) failed: \(failure.error)") }
                if self.state.deliveryUncertainSince != nil { self.scheduleUncertaintyRecovery(attempt: attempt + 1) } else { self.clearRecoveryScheduled() }
            }
        }
    }

    private func clearRecoveryScheduled() {
        lock.lock(); recoveryScheduled = false; lock.unlock()
    }

    /// The pod's history proves it started the pending bolus / temp basal: adopt the dose as if the reply had arrived.
    func handleStartEvent(_ event: PodEvent) {
        let snapshot = state
        guard let pending = snapshot.pendingCommand, !pending.executed else { return }
        switch (event, pending.kind) {
        case (.bolusStarted(let pulses), .bolus(let id, let wanted, let automatic)) where pulses == wanted:
            let units = UnitConversion.units(forPulses: Int(pulses))
            let dose = OpenPatchDose(kind: .bolus, id: id, units: units, startDate: pending.startedAt, duration: estimatedDuration(toBolus: units),
                                     automatic: automatic, insulinType: snapshot.insulinType)
            mutateState { $0.unfinalizedBolus = dose; $0.pendingCommand?.executed = true }
            reportDoses()
        case (.tempBasalStarted(let rate, let minutes), .tempBasal(let wantedRate, let wantedMinutes)) where rate == wantedRate && minutes == wantedMinutes:
            finalizeRunningTempBasal(cancelAt: pending.startedAt)
            let dose = OpenPatchDose(kind: .tempBasal, id: 0, units: UnitConversion.units(forPulses: Int(rate)), startDate: pending.startedAt,
                                     duration: TimeInterval(minutes) * 60, automatic: true, insulinType: snapshot.insulinType)
            mutateState { $0.unfinalizedTempBasal = dose; $0.pendingCommand?.executed = true }
            reportDoses()
        default:
            break
        }
    }

    /// Called by `reconcile` inside its state mutation: applies the pod's evidence to a pending command.
    /// Returns the decision and, for an idempotent command that cannot be verified, nothing is cleared (the caller resends it).
    func applyUncertaintyResolution(_ st: inout OpenPatchPumpManagerState, status: PodStatus) -> UncertaintyResolution? {
        guard st.deliveryUncertainSince != nil else { return nil }
        guard let pending = st.pendingCommand else { return nil }      // an old state without a command: only the user can clear it
        let decision = st.resolution(of: pending, status: status)
        switch decision {
        case .executed, .notExecuted:
            st.pendingCommand = nil
            st.deliveryUncertainSince = nil
        case .undecided, .resend:
            break
        }
        return decision
    }

    /// The pod does not report the basal program back: sending it again is idempotent and settles the question.
    func resendBasalProgram() {
        guard let program = state.basalProgram else { return }
        // the status that answers the resend is reconciled too and would ask for another resend: only one runs at a time
        lock.lock()
        if resendingBasalProgram { lock.unlock(); return }
        resendingBasalProgram = true
        lock.unlock()
        send(.setBasalProgram(program)) { [weak self] result in
            guard let self else { return }
            self.lock.lock(); self.resendingBasalProgram = false; self.lock.unlock()
            guard case .success = result else { return }
            self.mutateState {
                if case .basalProgram? = $0.pendingCommand?.kind { $0.pendingCommand = nil; $0.deliveryUncertainSince = nil }
            }
        }
    }
}
