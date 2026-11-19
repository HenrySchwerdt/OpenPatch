import Foundation
import OpenPatchCore

/// The delivery command whose reply was lost: the pod may or may not have executed it. Persisted, so an app restart does not
/// forget that the delivery state is uncertain. Resolved by the next status read plus the pod's history (`BolusStart` /
/// `TempStart` events are the proof of execution), see `OpenPatchPumpManager+Recovery.swift`. Loop and Trio rely on this:
/// `PumpManagerError.uncertainDelivery` is only a promise that the pump manager will find out.
public struct PendingCommand: Codable, Equatable {
    public enum Kind: Codable, Equatable {
        case bolus(id: UInt16, pulses: UInt16, automatic: Bool)
        case tempBasal(rateTicks: UInt16, minutes: UInt16)
        case cancelTempBasal
        case cancelBolus
        case suspend
        case resume
        /// A basal program was sent (idempotent: resolved by sending it again).
        case basalProgram
        case other
    }

    public var kind: Kind
    public var startedAt: Date
    /// History cursor when the command went out. `nil` = history was never synced: absence of events proves nothing.
    public var historyCursor: UInt32?
    /// The pod's history (or status) showed that it executed the command.
    public var executed = false

    public init(kind: Kind, startedAt: Date, historyCursor: UInt32?) {
        self.kind = kind; self.startedAt = startedAt; self.historyCursor = historyCursor
    }

    /// `nil` for commands that cannot leave the delivery uncertain.
    static func make(for command: Command, automatic: Bool, at date: Date, historyCursor: UInt32?) -> PendingCommand? {
        let kind: Kind
        switch command {
        case .bolus(let id, let pulses): kind = .bolus(id: id, pulses: pulses, automatic: automatic)
        case .setTempBasal(let ticks, let minutes): kind = .tempBasal(rateTicks: ticks, minutes: UInt16(min(max(((Int(minutes) + 29) / 30) * 30, 30), 720)))
        case .cancelTempBasal: kind = .cancelTempBasal
        case .cancelBolus: kind = .cancelBolus
        case .suspend: kind = .suspend
        case .resume, .confirmAttached: kind = .resume
        case .setBasalProgram: kind = .basalProgram
        default:
            guard command.affectsDelivery else { return nil }
            kind = .other
        }
        return PendingCommand(kind: kind, startedAt: date, historyCursor: historyCursor)
    }
}

/// What a status read (with the history read before it) says about a pending command.
enum UncertaintyResolution: Equatable {
    /// Cannot tell yet (history not fully read, or never synced): stays uncertain.
    case undecided
    case executed
    case notExecuted
    /// The command is idempotent and cannot be verified: send it again.
    case resend
}

extension OpenPatchPumpManagerState {
    /// Pure decision, no side effects: what does `status` (read after the history) say about `pending`?
    func resolution(of pending: PendingCommand, status: PodStatus) -> UncertaintyResolution {
        // The history is "fully read" when the cursor reached the pod's next event id (or the transport has no history at all).
        let caughtUp = status.historyNextEventID.map { (historyCursor ?? 0) >= $0 } ?? true
        let decidable = caughtUp && (pending.historyCursor != nil || status.historyNextEventID == nil)
        switch pending.kind {
        case .bolus(let id, _, _):
            let known = pending.executed || unfinalizedBolus?.id == id || unreportedFinishedDoses.contains { $0.kind == .bolus && $0.id == id }
            if known || status.bolus != nil { return .executed }
            return decidable ? .notExecuted : .undecided
        case .tempBasal(let rate, _):
            let known = pending.executed || (unfinalizedTempBasal.map { $0.startDate >= pending.startedAt.addingTimeInterval(-1) } ?? false)
            if known || status.tempBasal?.rateTicks == rate { return .executed }
            return decidable ? .notExecuted : .undecided
        case .cancelTempBasal: return status.tempBasal == nil ? .executed : .notExecuted
        case .cancelBolus: return status.bolus == nil ? .executed : .notExecuted
        case .suspend: return status.phase == .suspended ? .executed : .notExecuted
        case .resume: return status.phase == .active ? .executed : .notExecuted
        case .basalProgram: return .resend
        case .other: return .undecided
        }
    }
}
