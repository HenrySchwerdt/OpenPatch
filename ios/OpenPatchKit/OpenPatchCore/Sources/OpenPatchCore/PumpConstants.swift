import Foundation

/// Physical and protocol constants. Single source: spec/design-parameters.md (§4, §6, §7).
public enum PumpConstants {
    // The insulin volume per motor step is NOT a constant: see `DriveCalibration` (reported by the pod).
    /// Smallest commandable amount and wire quantum: 0.05 U ("pulse"). Roughly 2 steps on the 5:1 drive;
    /// the pod accumulates the remainder instead of rounding every pulse.
    public static let pulseUnits = 0.05
    /// Largest prime volume the pod accepts, in micro-units (0.524 U, protocol `OP_MAX_PRIME_MU`).
    public static let maxPrimeMicroUnits: UInt32 = 524_000
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
    /// Retraction rate of the assisted fill in motor steps per second (firmware `ASSISTED_FILL_PPS`, 200 pps).
    public static let assistedFillStepsPerSecond = 200
    /// After an assisted fill the first prime answers `Hourly` while the pod takes up the lost motion of the drive (firmware
    /// `PumpConfig::takeup_um`); the phone repeats it after the per-minute cap has recovered. Attempts and spacing.
    public static let primeTakeupMaxAttempts = 6
    public static let primeTakeupRetryDelay: TimeInterval = 61
    /// Pod raises a low-reservoir event below this level.
    public static let lowReservoirUnits = 10.0
    /// Domain-level protocol version (the wire frame version is `V1.version`).
    public static let protocolVersion: UInt8 = 1
}
