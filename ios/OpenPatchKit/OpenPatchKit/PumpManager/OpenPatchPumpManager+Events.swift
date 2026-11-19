import Foundation
import LoopKit
import OpenPatchCore

enum OpenPatchAlert: String {
    case lowReservoir, podFault, batteryLow, tempBasalCommLoss
    case podWearWarning, podWearExpired, spareNotReady, swapOldPodUnconfirmed, podConflict, podUndocked, podReleased, calibration

    var title: String {
        switch self {
        case .lowReservoir: return NSLocalizedString("Low insulin", bundle: .openPatchKit, comment: "Alert title")
        case .podFault: return NSLocalizedString("OpenPatch error", bundle: .openPatchKit, comment: "Alert title")
        case .batteryLow: return NSLocalizedString("Pod battery low", bundle: .openPatchKit, comment: "Alert title")
        case .tempBasalCommLoss: return NSLocalizedString("Connection lost", bundle: .openPatchKit, comment: "Alert title")
        case .podWearWarning: return NSLocalizedString("Pod wear time", bundle: .openPatchKit, comment: "Alert title")
        case .podWearExpired: return NSLocalizedString("Pod expired", bundle: .openPatchKit, comment: "Alert title")
        case .spareNotReady: return NSLocalizedString("Spare pod not ready", bundle: .openPatchKit, comment: "Alert title")
        case .swapOldPodUnconfirmed: return NSLocalizedString("Old pod not confirmed", bundle: .openPatchKit, comment: "Alert title")
        case .podConflict: return NSLocalizedString("Two active pods", bundle: .openPatchKit, comment: "Alert title")
        case .podUndocked: return NSLocalizedString("Pod not docked", bundle: .openPatchKit, comment: "Alert title")
        case .podReleased: return NSLocalizedString("Pod stopped", bundle: .openPatchKit, comment: "Alert title")
        case .calibration: return NSLocalizedString("Pod cannot be used", bundle: .openPatchKit, comment: "Alert title")
        }
    }
}

extension OpenPatchPumpManager {
    // MARK: Pod events

    func handle(event: PodEvent) {
        let now = Date()
        switch event {
        case .bolusCompleted(let id, let deliveredPulses):
            guard let bolus = state.unfinalizedBolus, bolus.id == id else { break }
            let delivered = UnitConversion.units(forPulses: Int(deliveredPulses))
            if delivered >= bolus.units - PumpConstants.pulseUnits / 2 {
                finalize(bolus: bolus.completed(deliveredUnits: bolus.units))
            } else {
                let fraction = bolus.units > 0 ? delivered / bolus.units : 0
                finalize(bolus: bolus.cancelled(at: bolus.startDate.addingTimeInterval(bolus.duration * fraction), deliveredUnits: delivered))
            }
        case .tempBasalEnded:
            if let temp = state.unfinalizedTempBasal { finalize(temp: temp.cancelled(at: min(now, temp.scheduledEnd))) }
        case .tempBasalRevertedCommLoss:
            if let temp = state.unfinalizedTempBasal { finalize(temp: temp.cancelled(at: now)) }
            issue(.tempBasalCommLoss, body: NSLocalizedString("The pod ended the temporary basal rate after losing contact with the phone.", bundle: .openPatchKit, comment: "Alert body"))
        case .lowReservoir(let pulses):
            mutateState { $0.reservoirUnits = UnitConversion.units(forPulses: Int(pulses)) }
            issue(.lowReservoir, body: String(format: NSLocalizedString("About %.0f U of insulin left.", bundle: .openPatchKit, comment: "Alert body"), UnitConversion.units(forPulses: Int(pulses))))
        case .fault(let code):
            mutateState { $0.faultCode = code; $0.phase = .faulted }
            issue(.podFault, body: String(format: NSLocalizedString("The pod stopped insulin delivery (%@). Replace or refill the pod.", bundle: .openPatchKit, comment: "Alert body"), "\(code)"))
            reportDoses(extra: [.openPatchAlarm(at: now, type: code == .occlusion ? .occlusion : (code == .reservoirEmpty ? .noInsulin : .other("\(code)")), title: "Pod fault: \(code)")])
        case .batteryLow(let percent):
            mutateState { $0.batteryFraction = Double(percent) / 100 }
            issue(.batteryLow, body: String(format: NSLocalizedString("Pod battery at %d %%. Charge the pod soon.", bundle: .openPatchKit, comment: "Alert body"), Int(percent)))
        case .primeCompleted:
            mutateState { if $0.phase == .priming { $0.phase = .primed } }
        case .docked(let docked):
            mutateState { $0.pair?.update($0.podRole ?? .a) { $0.isDocked = docked } }
            if !docked {
                if let bolus = state.unfinalizedBolus { finalize(bolus: bolus.cancelled(at: now)) }   // the pod cancels a running bolus when it loses the dock
                issue(.podUndocked, body: NSLocalizedString("The pod lost its dock contact. It delivers no insulin until it sits on the cannula again.", bundle: .openPatchKit, comment: "Alert body"))
            }
        case .wearWarning:
            raisedPairAlerts.insert("wearWarning")
            issue(.podWearWarning, body: NSLocalizedString("The pod has been worn for 44 hours. Swap to the other pod soon.", bundle: .openPatchKit, comment: "Alert body"))
        case .wearExpired:
            raisedPairAlerts.insert("wearExpired")
            mutateState { $0.faultCode = .wearExpired; $0.phase = .faulted }
            issue(.podWearExpired, body: NSLocalizedString("The pod reached its maximum wear time and stopped delivering insulin. Swap pods now.", bundle: .openPatchKit, comment: "Alert body"))
        case .diag, .diagCleared, .selfTest:
            break   // WP-6: per-code alerts, retraction, health view (docs/06-diagnostics.md 5.6); the legacy `.fault` event still drives `podFault`
        case .released(_, let reason):
            // The pod stopped on its own (charger / wear / a Release we did not see answered): never keep showing "active".
            if let bolus = state.unfinalizedBolus { finalize(bolus: bolus.cancelled(at: now)) }
            finalizeRunningTempBasal(cancelAt: now)
            mutateState { if $0.phase == .active || $0.phase == .suspended { $0.phase = .deactivated }; $0.podReportsActive = false }
            reportDoses(extra: [.openPatchSuspend(at: now)])
            if reason != .command {
                issue(.podReleased, body: NSLocalizedString("The pod stopped delivering insulin (it was put on a charger or reached its wear limit). Swap pods.", bundle: .openPatchKit, comment: "Alert body"))
            }
        }
        scheduleFinalization()
    }

    func issue(_ alert: OpenPatchAlert, body: String) {
        let content = Alert.Content(title: alert.title, body: body,
                                    acknowledgeActionButtonLabel: NSLocalizedString("OK", bundle: .openPatchKit, comment: "Alert button"))
        let critical = alert == .podFault
        let alert = Alert(identifier: Alert.Identifier(managerIdentifier: Self.pluginIdentifier, alertIdentifier: alert.rawValue),
                          foregroundContent: content, backgroundContent: content, trigger: .immediate,
                          interruptionLevel: critical ? .critical : .timeSensitive)
        delegate.notify { $0?.issueAlert(alert) }
    }

    // MARK: Reconciliation with a pod status

    /// Folds a pod status into the persisted state: telemetry, lifecycle, and any dose the pod no longer reports.
    func reconcile(with status: PodStatus, at now: Date) {
        mutateState { st in
            st.reservoirUnits = status.reservoirUnits
            st.batteryFraction = Double(status.batteryPercent) / 100
            st.lastSync = now
            st.faultCode = status.faultCode
            st.lastPodTotalDeliveredUnits = status.totalDeliveredUnits
            st.driveCalibration = status.driveCalibration
            st.calibrationProblem = CalibrationProblem.check(status.driveCalibration)
            st.podReportsActive = status.pairing?.isActive
            if let role = st.podRole { st.pair?.update(role) { $0.update(from: status, at: now) } }
            // Do not let a stale poll downgrade a lifecycle step we drive ourselves.
            if status.phase != .unpaired || st.phase == .unpaired { st.phase = status.phase }
            if status.phase == .suspended, st.suspendedAt == nil { st.suspendedAt = now }
            if status.phase == .active { st.suspendedAt = nil }

            if let bolus = st.unfinalizedBolus, status.bolus?.id != bolus.id {
                let ended = bolus.isFinished(at: now) ? bolus.completed(deliveredUnits: bolus.units) : bolus.cancelled(at: now)
                st.unreportedFinishedDoses.append(ended)
                st.unfinalizedBolus = nil
            }
            if st.unfinalizedBolus == nil, let adopted = status.bolus {
                // A bolus we lost the reply for (or one started by another client) is running on the pod: adopt it.
                let units = UnitConversion.units(forPulses: Int(adopted.requestedPulses))
                let done = UnitConversion.units(forPulses: Int(adopted.deliveredPulses))
                let duration = UnitConversion.bolusDuration(forUnits: units)
                st.unfinalizedBolus = OpenPatchDose(kind: .bolus, id: adopted.id, units: units,
                                                    startDate: now.addingTimeInterval(-UnitConversion.bolusDuration(forUnits: done)),
                                                    duration: duration, automatic: false, insulinType: st.insulinType)
                st.deliveryUncertainSince = nil
            }
            if st.unfinalizedTempBasal == nil, let adopted = status.tempBasal, adopted.remainingMinutes > 0,
               adoptTempBasalFromNextStatus || st.deliveryUncertainSince != nil {
                // A temp basal handed over by a swap (or whose reply we lost) runs on the pod: adopt it.
                st.unfinalizedTempBasal = OpenPatchDose(kind: .tempBasal, id: 0, units: adopted.unitsPerHour, startDate: now,
                                                        duration: TimeInterval(adopted.remainingMinutes) * 60, automatic: true, insulinType: st.insulinType)
            }
            if let temp = st.unfinalizedTempBasal, status.tempBasal == nil {
                let ended = temp.isFinished(at: now) ? temp : temp.cancelled(at: now)
                st.unreportedFinishedDoses.append(ended)
                st.unfinalizedTempBasal = nil
            }
        }
        adoptTempBasalFromNextStatus = false
        reportReservoir()
        if !state.unreportedFinishedDoses.isEmpty { reportDoses() }
        scheduleFinalization()
    }

    // MARK: Dose bookkeeping

    func finalize(bolus: OpenPatchDose) {
        lock.lock(); lastFinalizedBolus = bolus; lock.unlock()
        mutateState { st in
            guard st.unfinalizedBolus?.id == bolus.id else { return }
            st.unreportedFinishedDoses.append(bolus)
            st.unfinalizedBolus = nil
        }
        reportDoses()
    }

    func finalize(temp: OpenPatchDose) {
        mutateState { st in
            guard st.unfinalizedTempBasal?.startDate == temp.startDate else { return }
            st.unreportedFinishedDoses.append(temp)
            st.unfinalizedTempBasal = nil
        }
        reportDoses()
    }

    /// Ends a running temp basal locally (without reporting, the caller reports once).
    func finalizeRunningTempBasal(cancelAt date: Date) {
        mutateState { st in
            guard let temp = st.unfinalizedTempBasal else { return }
            st.unreportedFinishedDoses.append(temp.isFinished(at: date) ? temp : temp.cancelled(at: date))
            st.unfinalizedTempBasal = nil
        }
    }

    /// Doses whose scheduled end has passed are finalised locally even if the pod is out of range.
    func finalizeExpiredDoses(now: Date = Date()) {
        mutateState { st in
            if let bolus = st.unfinalizedBolus, bolus.isFinished(at: now) {
                st.unreportedFinishedDoses.append(bolus); st.unfinalizedBolus = nil
            }
            if let temp = st.unfinalizedTempBasal, temp.isFinished(at: now) {
                st.unreportedFinishedDoses.append(temp); st.unfinalizedTempBasal = nil
            }
        }
        if !state.unreportedFinishedDoses.isEmpty { reportDoses() }
        scheduleFinalization()
    }

    func scheduleFinalization() {
        finalizationItem?.cancel()
        let st = state
        let next = [st.unfinalizedBolus?.scheduledEnd, st.unfinalizedTempBasal?.scheduledEnd].compactMap { $0 }.min()
        guard let next else { return }
        let item = DispatchWorkItem { [weak self] in self?.finalizeExpiredDoses() }
        finalizationItem = item
        workQueue.asyncAfter(deadline: .now() + max(next.timeIntervalSinceNow, 0) + 1, execute: item)
    }

    // MARK: Reporting to the host

    /// Reports finished doses (immutable) plus everything still in flight (mutable) and replaces pending events.
    /// Finished doses are replayed until the host confirms, so a failed `hasNewPumpEvents` loses nothing.
    func reportDoses(extra: [NewPumpEvent] = []) {
        let st = state
        let now = Date()
        var events = st.unreportedFinishedDoses.map { NewPumpEvent.openPatch(dose: $0, isMutable: false, at: now) }
        events.append(contentsOf: extra)
        if let bolus = st.unfinalizedBolus { events.append(.openPatch(dose: bolus, isMutable: true, at: now)) }
        if let temp = st.unfinalizedTempBasal { events.append(.openPatch(dose: temp, isMutable: true, at: now)) }
        let reportedCount = st.unreportedFinishedDoses.count
        let reconciliation = st.lastSync

        delegate.notify { [weak self] delegate in
            guard let self, let delegate else { return }
            delegate.pumpManager(self, hasNewPumpEvents: events, lastReconciliation: reconciliation, replacePendingEvents: true) { error in
                if let error { self.log("hasNewPumpEvents failed: \(error)"); return }
                self.mutateState { $0.unreportedFinishedDoses.removeFirst(min(reportedCount, $0.unreportedFinishedDoses.count)) }
            }
        }
    }

    func reportReservoir() {
        guard let units = state.reservoirUnits else { return }
        delegate.notify { [weak self] delegate in
            guard let self else { return }
            delegate?.pumpManager(self, didReadReservoirValue: units, at: Date()) { _ in }
        }
    }

    // MARK: Delivery uncertainty

    public func clearDeliveryUncertainty() {
        mutateState { $0.deliveryUncertainSince = nil }
    }
}

extension OpenPatchDose {
    func completed(deliveredUnits: Double) -> OpenPatchDose {
        var copy = self
        copy.deliveredUnitsOverride = deliveredUnits
        return copy
    }
}
