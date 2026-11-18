import Foundation

public enum CommandKind: Equatable, CaseIterable {
    case hello, getStatus, setTime, setBasalProgram, setLimits
    case bolus, cancelBolus, setTempBasal, cancelTempBasal, suspend, resume
    case confirmFill, prime, confirmAttached, deactivate, silenceAlarm
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
        }
    }

    /// True if losing the reply leaves the app unsure whether insulin delivery changed.
    public var affectsDelivery: Bool {
        switch kind {
        case .bolus, .cancelBolus, .setTempBasal, .cancelTempBasal, .suspend, .resume, .setBasalProgram: return true
        default: return false
        }
    }
}
