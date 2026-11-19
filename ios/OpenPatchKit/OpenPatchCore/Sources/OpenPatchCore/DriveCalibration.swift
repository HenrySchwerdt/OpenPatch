import Foundation

/// How much insulin one motor step delivers. SAFETY CRITICAL: this scales every step-based quantity
/// (priming, simulator, step counters) and is NOT a compile-time constant: it depends on the drive
/// that is built into the pod and is reported by the pod in `GetStatus` (`DRIVE_CAL`, protocol 3.3).
///
/// History: the 10:1 concept (0.0131 U/step) was replaced by the Rev A 5:1 gear (0.0261 U/step). An app that
/// still assumed the old value would command twice the intended prime volume, and any code that converts
/// steps to insulin would be off by a factor of two. There is deliberately no global "units per step" any more.
public struct DriveCalibration: Equatable, Hashable, Codable {
    public let driveID: UInt16
    /// Micro-units (1e-6 U) of insulin per motor step.
    public let microUnitsPerStep: UInt32
    public let stepsPerRevolution: UInt16
    /// Gearbox ratio times 100 (5:1 = 500).
    public let gearRatioTimes100: UInt16

    public init(driveID: UInt16, microUnitsPerStep: UInt32, stepsPerRevolution: UInt16, gearRatioTimes100: UInt16) {
        self.driveID = driveID
        self.microUnitsPerStep = microUnitsPerStep
        self.stepsPerRevolution = stepsPerRevolution
        self.gearRatioTimes100 = gearRatioTimes100
    }

    /// Rev A: Zhaowei ZWBPD006006, 20 steps/rev, 5:1 planetary gear: 0.261 µl = 0.0261 U per step (spec §4).
    public static let zwbpd006006_5_1 = DriveCalibration(driveID: 1, microUnitsPerStep: 26_100, stepsPerRevolution: 20, gearRatioTimes100: 500)
    /// Premium: Faulhaber ADM0620 + 06/1 16:1: 0.0082 U per step (~122.6 steps/U).
    public static let faulhaber_16_1 = DriveCalibration(driveID: 2, microUnitsPerStep: 8_156, stepsPerRevolution: 20, gearRatioTimes100: 1600)

    /// Rust bench pod (current CAD): NFP-608-26.45 + GHW 16:20 step-down pair, total ratio 33.0625, 2 088 800 / 529 uU = 3 948.6 uU
    /// per step (the pod reports the floor, 3 948; the ratio x 100 is rounded, 3306). Firmware id 0x25.
    public static let nfp608_26_45_g16_20 = DriveCalibration(driveID: 0x25, microUnitsPerStep: 3_948, stepsPerRevolution: 20, gearRatioTimes100: 3_306)

    /// The only drives the app accepts: the two legacy C reference drives plus every production preset of `firmware-rs`
    /// (`openpatch-core/src/drive_cal.rs`; a Swift test parses that file and checks this table against it). A pod
    /// reporting anything else is refused: the volume per step would be a guess.
    public static let known: [DriveCalibration] = [.zwbpd006006_5_1, .faulhaber_16_1] + firmwarePresets

    public var isKnown: Bool { Self.known.contains(self) }

    public var unitsPerStep: Double { Double(microUnitsPerStep) / 1_000_000 }

    /// Lead-screw travel per motor step (M1.6 x 0.35 spindle), in micrometres: 5:1 -> 3.5, 16:1 -> 1.09375.
    public var micrometresPerStep: Double {
        350.0 / (Double(stepsPerRevolution) * Double(gearRatioTimes100) / 100.0)
    }

    /// Largest prime the pod accepts: 0.524 U (needle dead volume only), in whole steps.
    public var maxPrimeSteps: Int { Int(PumpConstants.maxPrimeMicroUnits / UInt32(max(microUnitsPerStep, 1))) }
}

public enum CalibrationProblem: Error, Equatable, Codable {
    /// The pod did not report a calibration (old firmware, all zero, or it has none).
    case missing
    /// The pod reported a calibration that is not one of `DriveCalibration.known`.
    case unknown(driveID: UInt16, microUnitsPerStep: UInt32)

    /// `nil` means the calibration is present and known.
    public static func check(_ calibration: DriveCalibration?) -> CalibrationProblem? {
        guard let calibration else { return .missing }
        return calibration.isKnown ? nil : .unknown(driveID: calibration.driveID, microUnitsPerStep: calibration.microUnitsPerStep)
    }
}
