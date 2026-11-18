import Foundation

/// Two-pod system (spec/design-parameters.md §1b): the user owns two identical pods, A and B.
/// One is docked on the cannula and delivers; the other is charged and refilled. Only one may ever deliver.
public enum PodRole: UInt8, Codable, Equatable, CaseIterable {
    case a = 1
    case b = 2

    public var other: PodRole { self == .a ? .b : .a }
    public var label: String { self == .a ? "A" : "B" }
}

/// What the pod itself says about delivery (wire `POD_INFO.delivery_state`).
public enum PodDeliveryState: UInt8, Codable, Equatable {
    /// Not the active pod: never delivers, refuses delivery commands.
    case released = 0
    /// Active and docked.
    case active = 1
    /// Active but undocked: no step is executed (hardware hard gate).
    case pausedUndocked = 2
    /// Wear limit reached: delivery stopped.
    case stoppedWear = 3
}

/// Pair / dock / wear information reported in every status of a two-pod capable pod.
public struct PodPairingInfo: Equatable {
    public var pairID: UInt32
    public var role: PodRole?
    public var deliveryState: PodDeliveryState
    public var isDocked: Bool
    public var isActive: Bool
    public var wearSeconds: UInt32
    /// 44 h reached (pod flag).
    public var wearWarning: Bool

    public init(pairID: UInt32, role: PodRole?, deliveryState: PodDeliveryState, isDocked: Bool, isActive: Bool,
                wearSeconds: UInt32, wearWarning: Bool = false) {
        self.pairID = pairID; self.role = role; self.deliveryState = deliveryState
        self.isDocked = isDocked; self.isActive = isActive; self.wearSeconds = wearSeconds; self.wearWarning = wearWarning
    }

    public var wear: TimeInterval { TimeInterval(wearSeconds) }
}

public enum WearPolicy {
    /// Warning at 44 h, delivery stop + alarm at 52 h (spec §1b). Nominal wear time 48 h.
    public static let warning: TimeInterval = 44 * 3600
    public static let stop: TimeInterval = 52 * 3600
    public static let nominal: TimeInterval = 48 * 3600
}

/// Result of `releasePod`: what the old pod delivered and what is left in it.
public struct ReleaseReport: Equatable, Codable {
    public var deliveredSinceActivationUnits: Double
    public var finalReservoirUnits: Double
    public init(deliveredSinceActivationUnits: Double, finalReservoirUnits: Double) {
        self.deliveredSinceActivationUnits = deliveredSinceActivationUnits
        self.finalReservoirUnits = finalReservoirUnits
    }
}
