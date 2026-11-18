import Foundation

/// Reservoir variants (§1/§3). They differ only in length.
public enum PodSize: Int, CaseIterable, Codable, Identifiable {
    case u70 = 70
    case u100 = 100
    case u200 = 200

    public var id: Int { rawValue }
    public var capacityUnits: Double { Double(rawValue) }
    /// Piston stroke from spec §3 (without the 1.0 mm dead-volume reserve).
    public var strokeMillimetres: Double {
        switch self {
        case .u70: return 9.4
        case .u100: return 13.4
        case .u200: return 26.8
        }
    }
    public static let minimumFillUnits = 10.0

    public var displayName: String { "OP-\(rawValue)" }

    public func validateFill(units: Double) throws {
        if units + 1e-9 < Self.minimumFillUnits { throw FillError.tooSmall(minimum: Self.minimumFillUnits) }
        if units > capacityUnits + 1e-9 { throw FillError.tooLarge(maximum: capacityUnits) }
    }
}

public enum FillError: Error, Equatable {
    case tooSmall(minimum: Double)
    case tooLarge(maximum: Double)
}
