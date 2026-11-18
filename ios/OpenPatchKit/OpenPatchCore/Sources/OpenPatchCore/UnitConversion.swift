import Foundation

/// Conversions between insulin units, 0.05 U pulses and motor steps.
public enum UnitConversion {
    /// Tolerance for binary floating point (0.15 / 0.05 = 2.9999999999999996).
    private static let epsilon = 1e-9

    public static func steps(forUnits units: Double) -> Int {
        guard units > 0 else { return 0 }
        return Int((units / PumpConstants.unitsPerStep).rounded())
    }

    public static func units(forSteps steps: Int) -> Double {
        Double(steps) * PumpConstants.unitsPerStep
    }

    /// Number of whole 0.05 U pulses contained in `units` (floor).
    public static func pulses(forUnits units: Double) -> Int {
        guard units > 0 else { return 0 }
        return Int((units / PumpConstants.pulseUnits + epsilon).rounded(.down))
    }

    public static func units(forPulses pulses: Int) -> Double {
        Double(pulses) / 20.0   // exact for the 0.05 grid, no 0.15000000000000002
    }

    /// Rounds down to the 0.05 U grid. Used for bolus volumes and basal rates (never exceeds the request).
    public static func roundDownToPulse(_ units: Double) -> Double {
        self.units(forPulses: pulses(forUnits: units))
    }

    public static func bolusDuration(forUnits units: Double, unitsPerMinute: Double = PumpConstants.bolusUnitsPerMinute) -> TimeInterval {
        units / unitsPerMinute * 60
    }

    /// 0.05, 0.10 ... `maximum`
    public static func supportedVolumes(maximum: Double) -> [Double] {
        let count = pulses(forUnits: maximum)
        return (1...max(count, 1)).map { units(forPulses: $0) }
    }
}

/// Converts a stream of small unit amounts to whole motor steps and carries the fractional rest,
/// so that e.g. 100 x 0.05 U delivers 5.0 U (+-1 step) instead of 4 x 100 steps = 5.24 U.
public struct StepAccumulator: Equatable, Codable {
    public private(set) var remainder: Double

    public init(remainder: Double = 0) { self.remainder = remainder }

    public mutating func steps(forUnits units: Double) -> Int {
        guard units > 0 else { return 0 }
        let total = remainder + units / PumpConstants.unitsPerStep
        let whole = Int((total + 1e-9).rounded(.down))
        remainder = max(total - Double(whole), 0)
        return whole
    }

    public mutating func reset() { remainder = 0 }
}
