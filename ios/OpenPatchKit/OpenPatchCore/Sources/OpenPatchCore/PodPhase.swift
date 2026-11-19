import Foundation

/// Lifecycle of a reusable pod. Pure transition table, no side effects.
public enum PodPhase: UInt8, CaseIterable, Codable, Equatable {
    case unpaired = 0
    case paired = 1        // BLE bonded, reservoir empty, waiting for syringe fill
    case filled = 2        // fill confirmed, waiting for prime
    case priming = 3
    case primed = 4        // ready to snap onto the cannula head
    case active = 5        // delivering
    case suspended = 6
    case faulted = 7
    case deactivated = 8   // removed from body; can be refilled and reused
}

public enum LifecycleEvent: Equatable {
    case paired, fillConfirmed, primeStarted, primeCompleted, attached
    case suspended, resumed, faulted, deactivated, refillRequested, reset
}

public enum PodLifecycle {
    public static func transition(from phase: PodPhase, event: LifecycleEvent) -> PodPhase? {
        switch (phase, event) {
        case (_, .reset): return .unpaired
        case (.unpaired, .paired): return .paired
        case (.paired, .fillConfirmed): return .filled
        case (.filled, .primeStarted): return .priming
        case (.priming, .primeCompleted): return .primed
        case (.primed, .attached): return .active
        case (.active, .suspended): return .suspended
        case (.suspended, .resumed): return .active
        case (.paired, .faulted), (.filled, .faulted), (.priming, .faulted), (.primed, .faulted),
             (.active, .faulted), (.suspended, .faulted): return .faulted
        case (.paired, .deactivated), (.filled, .deactivated), (.priming, .deactivated), (.primed, .deactivated),
             (.active, .deactivated), (.suspended, .deactivated), (.faulted, .deactivated): return .deactivated
        case (.deactivated, .refillRequested), (.faulted, .refillRequested), (.suspended, .refillRequested): return .paired
        default: return nil
        }
    }
}

public extension PodPhase {
    func allows(_ kind: CommandKind) -> Bool {
        switch kind {
        case .hello, .getStatus, .setTime, .silenceAlarm: return true
        case .setBasalProgram, .setLimits: return self != .unpaired
        case .confirmFill: return self == .paired
        case .prime: return self == .filled
        case .confirmAttached: return self == .primed
        case .bolus, .setTempBasal: return self == .active
        case .cancelBolus, .cancelTempBasal: return self == .active || self == .suspended
        case .suspend: return self == .active
        case .resume: return self == .suspended
        case .deactivate: return self != .unpaired && self != .deactivated
        case .setPairing: return self != .unpaired && self != .active && self != .suspended
        case .activatePod: return self == .filled
        case .releasePod: return self != .unpaired
        case .assistedFill: return self == .paired || self == .filled
        case .cancelAssistedFill: return true
        }
    }

    var isDelivering: Bool { self == .active }
}
