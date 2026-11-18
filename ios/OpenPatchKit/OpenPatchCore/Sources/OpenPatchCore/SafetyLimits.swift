import Foundation

public enum LimitError: Error, Equatable {
    case notPositive
    case bolusTooLarge
    case basalRateTooHigh
    case invalidDuration
    case hourlyLimit
}

/// Pod-side delivery limits (§7). Firmware enforces them independently of the app; the app checks first
/// to produce readable errors. `maxBolus`/`maxBasalRate` are user-configurable up to the hard caps.
public struct SafetyLimits: Equatable, Codable {
    public static let absoluteMaxBolus = 25.0
    public static let absoluteMaxBasalRate = 30.0
    public static let defaultMaxBolus = 10.0
    public static let defaultMaxBasalRate = 5.0

    public let maxBolus: Double
    public let maxBasalRate: Double
    public let maxHourlyDelivery = 15.0
    public let bolusUnitsPerMinute = PumpConstants.bolusUnitsPerMinute
    public let occlusionThresholdUnits = 2.0
    /// After communication loss a temp basal keeps running at most this long (DASH semantics).
    public let commLossTempBasalLimit: TimeInterval = 30 * 60

    public static let `default` = SafetyLimits()

    public init(maxBolus: Double = defaultMaxBolus, maxBasalRate: Double = defaultMaxBasalRate) {
        self.maxBolus = min(max(maxBolus, 0), Self.absoluteMaxBolus)
        self.maxBasalRate = min(max(maxBasalRate, 0), Self.absoluteMaxBasalRate)
    }

    private enum CodingKeys: String, CodingKey { case maxBolus, maxBasalRate }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(maxBolus: try c.decode(Double.self, forKey: .maxBolus),
                  maxBasalRate: try c.decode(Double.self, forKey: .maxBasalRate))
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(maxBolus, forKey: .maxBolus)
        try c.encode(maxBasalRate, forKey: .maxBasalRate)
    }

    private static let epsilon = 1e-9

    public func validateBolus(units: Double) throws {
        guard units > 0 else { throw LimitError.notPositive }
        guard units <= maxBolus + Self.epsilon else { throw LimitError.bolusTooLarge }
    }

    public func validateTempBasal(unitsPerHour: Double, duration: TimeInterval) throws {
        guard unitsPerHour >= 0 else { throw LimitError.notPositive }
        guard unitsPerHour <= maxBasalRate + Self.epsilon else { throw LimitError.basalRateTooHigh }
        guard duration > 0, duration <= PumpConstants.maxTempBasalDuration else { throw LimitError.invalidDuration }
    }

    public func validateHourly(requested: Double, alreadyDelivered: Double) throws {
        guard requested + alreadyDelivered <= maxHourlyDelivery + Self.epsilon else { throw LimitError.hourlyLimit }
    }
}
