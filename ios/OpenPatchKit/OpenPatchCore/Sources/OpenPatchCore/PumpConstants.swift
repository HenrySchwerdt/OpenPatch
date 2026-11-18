import Foundation

/// Physical and protocol constants. Single source: spec/design-parameters.md (§4, §6, §7).
public enum PumpConstants {
    /// Insulin volume per motor step: 0.131 µl at U100 = 0.0131 U (§4).
    public static let unitsPerStep = 0.0131
    /// Lead-screw travel per motor step in micrometres (0.35 mm / (20 steps * 10:1)) (§4).
    public static let micrometresPerStep = 1.75
    /// Smallest commandable amount and wire quantum: 0.05 U ("pulse"). Nominally 4 steps (3.82).
    public static let pulseUnits = 0.05
    /// Nominal steps per pulse. The pod accumulates the remainder instead of rounding every pulse.
    public static let nominalStepsPerPulse = 4
    /// Bolus speed (§7).
    public static let bolusUnitsPerMinute = 1.5
    /// Basal schedule resolution: 48 half-hour slots.
    public static let basalSlotCount = 48
    public static let basalSlotDuration: TimeInterval = 1800
    /// Wire protocol v1 accepts 1-24 basal segments (same as Omnipod DASH).
    public static let maxBasalSegments = 24
    /// Longest temp basal accepted (12 h, same as most pumps).
    public static let maxTempBasalDuration: TimeInterval = 12 * 3600
    /// Priming placeholder values: tune after first wet test.
    public static let primeUnits = 0.5
    public static let primeDuration: TimeInterval = 40
    /// Pod raises a low-reservoir event below this level.
    public static let lowReservoirUnits = 10.0
    /// Domain-level protocol version (the wire frame version is `V1.version`).
    public static let protocolVersion: UInt8 = 1
}
