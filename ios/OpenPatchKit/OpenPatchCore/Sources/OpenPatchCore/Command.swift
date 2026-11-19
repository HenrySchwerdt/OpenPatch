import Foundation

public enum CommandKind: Equatable, CaseIterable {
    case hello, getStatus, setTime, setBasalProgram, setLimits
    case bolus, cancelBolus, setTempBasal, cancelTempBasal, suspend, resume
    case confirmFill, prime, confirmAttached, deactivate, silenceAlarm
    case setPairing, activatePod, releasePod
    case assistedFill, cancelAssistedFill
}

/// Phone -> pod commands. Amounts are integer pulses (0.05 U) / ticks (0.05 U/h) so the wire
/// never carries floating point.
public enum Command: Equatable {
    case hello(protocolVersion: UInt8, time: Date, utcOffsetMinutes: Int16)
    case getStatus
    case setTime(Date, utcOffsetMinutes: Int16)
    case setBasalProgram(BasalProgram)
    case setLimits(SafetyLimits)
    case bolus(id: UInt16, pulses: UInt16)
    case cancelBolus
    case setTempBasal(rateTicks: UInt16, durationMinutes: UInt16)
    case cancelTempBasal
    case suspend
    case resume
    case confirmFill(pulses: UInt16)
    case prime
    case confirmAttached
    case deactivate
    case silenceAlarm
    /// Two-pod: store pair ID + role (released pods only).
    case setPairing(pairID: UInt32, role: PodRole)
    /// Two-pod: become the active pod. The pod must be docked, filled and paired; delivery stays suspended until
    /// `confirmAttached` (after the connector prime). `tempBasal` = remaining temp basal handed over from the old pod.
    case activatePod(pairID: UInt32, activationID: UInt32, program: BasalProgram, tempBasal: HandoverTempBasal?)
    /// Two-pod: stop delivering and return the totals. Idempotent.
    case releasePod(pairID: UInt32)
    /// Refill: the pod retracts its plunger by `pulses` x 0.05 U at a fixed rate while the user pushes the syringe
    /// (assisted pressure fill). Only an undocked, suspended pod; progress arrives in `PodStatus.fill`.
    case assistedFill(pulses: UInt16)
    /// Stops a running fill; the volume drawn so far stays booked.
    case cancelAssistedFill

    public var kind: CommandKind {
        switch self {
        case .hello: return .hello
        case .getStatus: return .getStatus
        case .setTime: return .setTime
        case .setBasalProgram: return .setBasalProgram
        case .setLimits: return .setLimits
        case .bolus: return .bolus
        case .cancelBolus: return .cancelBolus
        case .setTempBasal: return .setTempBasal
        case .cancelTempBasal: return .cancelTempBasal
        case .suspend: return .suspend
        case .resume: return .resume
        case .confirmFill: return .confirmFill
        case .prime: return .prime
        case .confirmAttached: return .confirmAttached
        case .deactivate: return .deactivate
        case .silenceAlarm: return .silenceAlarm
        case .setPairing: return .setPairing
        case .activatePod: return .activatePod
        case .releasePod: return .releasePod
        case .assistedFill: return .assistedFill
        case .cancelAssistedFill: return .cancelAssistedFill
        }
    }

    /// True if losing the reply leaves the app unsure whether insulin delivery changed.
    public var affectsDelivery: Bool {
        switch kind {
        case .bolus, .cancelBolus, .setTempBasal, .cancelTempBasal, .suspend, .resume, .setBasalProgram, .activatePod, .releasePod: return true
        default: return false
        }
    }
}

/// Temp basal that was running on the old pod, handed to the new one (remaining duration, rounded up to 30 min on the wire).
public struct HandoverTempBasal: Equatable {
    public var rateTicks: UInt16
    public var remainingMinutes: UInt16
    public init(rateTicks: UInt16, remainingMinutes: UInt16) { self.rateTicks = rateTicks; self.remainingMinutes = remainingMinutes }
}
