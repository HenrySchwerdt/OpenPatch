import Foundation

/// The drive presets of the Rust pod firmware (`firmware-rs/openpatch-core/src/drive_cal.rs`), by their wire id.
///
/// The pod reports `DRIVE_CAL = (id, floor of uU per step, steps per revolution, ratio x 100)`; the app accepts exactly these
/// tuples (`DriveCalibration.known`) and nothing else. Which presets exist, their ids and their numbers are checked against
/// the firmware source by `FirmwarePresetParityTests`.
public extension DriveCalibration {
    /// v0.1.0 cup pod: NFP-608-26.45 -> miter pair z16:z16 (1:1) -> rod into a cup plunger in a 20.5 x 5.5 mm stadium bore:
    /// 840 503 125 / 119 554 uU = 7 030.3 uU per step (0.00703 U, 142 steps per U). NO check valve, never aspirates.
    static let nfp608_26_45_cupMiter1_1 = DriveCalibration(driveID: 0x26, microUnitsPerStep: 7_030, stepsPerRevolution: 20, gearRatioTimes100: 2_645)
    /// The firmware presets the app accepts: the drives of pods that are actually built (`mechanical/`): the 16:20 step-down pod
    /// and the v0.1.0 cup pod. The other firmware presets (0x20 coaxial, 0x21 / 0x22 Zhaowei, 0x23 Faulhaber, 0x24 15:12 pair,
    /// 0x30 syringe rig) are REFUSED on purpose: no pod is built with them, and a pod that reports one is a wrong or foreign
    /// build whose volume per step must not be trusted (the 15:12 pair would dose +56 %).
    static let firmwarePresets: [DriveCalibration] = [.nfp608_26_45_g16_20, .nfp608_26_45_cupMiter1_1]

    /// Firmware presets that exist but are not accepted by the app, with the reason (checked by `FirmwareParityTests`).
    static let refusedFirmwarePresetIDs: [UInt16: String] = [
        0x20: "coaxial NFP-608: not the current CAD", 0x21: "Zhaowei 6.43: no pod built", 0x22: "Zhaowei 4.8: no pod built",
        0x23: "Faulhaber ADM0620: no pod built", 0x24: "15:12 gear pair: does not fit the carriage lane (+56 % dose)",
        0x30: "syringe bench rig: no pod",
    ]

    /// Preset name as printed in the firmware documentation and shown in the settings (`nil` = not a known drive).
    var presetName: String? {
        guard isKnown else { return nil }
        switch driveID {
        case 1: return "zwbpd006006-5-1 (legacy)"
        case 2: return "faulhaber-adm0620-16-1 (legacy)"
        case 0x25: return "nfp-608-26-45-g16-20"
        case 0x26: return "nfp-608-26-45-cup-miter-1-1"
        default: return nil
        }
    }

    /// The pod aspirates by itself only on drives with a check valve. The cup pod has none: a suction draw could pull
    /// from the cannula side, so the app never offers it and the firmware refuses it (`Preset::allows_draw`).
    /// An unknown calibration never allows it either.
    var allowsSuctionDraw: Bool {
        guard isKnown else { return false }
        switch driveID {
        case 0x26: return false
        case 1, 2: return false     // the C reference has no draw at all
        default: return true        // 0x25: has a check valve
        }
    }

    /// Whether the pod understands the `AssistedFill` command (Rust firmware presets only).
    var supportsAssistedFill: Bool { isKnown && driveID >= 0x20 }

    /// Fill methods the app may offer for this drive, preferred first. Empty = unknown drive: no fill at all.
    var allowedFillModes: [FillMode] {
        guard isKnown else { return [] }
        guard supportsAssistedFill else { return [.manualConfirm] }
        return allowsSuctionDraw ? [.assistedPressure, .suctionDraw] : [.assistedPressure]
    }

    /// Nominal retraction rate of the assisted fill (firmware `ASSISTED_FILL_PPS`), as units per second.
    var assistedFillUnitsPerSecond: Double { Double(PumpConstants.assistedFillStepsPerSecond) * unitsPerStep }

    /// Volume of `units` rounded DOWN to whole motor steps: what the pod delivers when it quantises to its step (the
    /// pod carries the fractional step over into the next dose, so over many doses nothing is lost).
    func quantizedUnits(_ units: Double) -> Double {
        guard units > 0, microUnitsPerStep > 0 else { return 0 }
        let steps = (units / unitsPerStep + 1e-9).rounded(.down)
        return steps * unitsPerStep
    }
}

/// How the pod gets its insulin (water on the bench).
public enum FillMode: Equatable, Codable {
    /// Assisted PRESSURE fill: the user pushes the syringe, the pod retracts its plunger at a fixed rate. The only mode
    /// of the cup pod.
    case assistedPressure
    /// Suction draw: the pod pulls from a vial by itself. Only on drives with a check valve; never on the cup pod.
    case suctionDraw
    /// Legacy C reference pods: the user injects by hand and confirms the amount.
    case manualConfirm
}

/// What the pod reports about its fill / draw job (`DRAW_STATE`, `DRAW_REQUESTED_MU`, `DRAW_DONE_MU`).
public enum FillState: UInt8, Equatable, Codable {
    case idle = 0, drawing = 1, done = 2, stalled = 3, aborted = 4
}

public struct FillStatus: Equatable, Codable {
    public var state: FillState
    public var requestedUnits: Double
    /// Volume the pod confirmed so far (step-exact and sensor-confirmed).
    public var drawnUnits: Double
    /// The mandatory prime has not been done since this fill.
    public var primeRequired: Bool

    public init(state: FillState, requestedUnits: Double, drawnUnits: Double, primeRequired: Bool) {
        self.state = state; self.requestedUnits = requestedUnits; self.drawnUnits = drawnUnits; self.primeRequired = primeRequired
    }

    public var isRunning: Bool { state == .drawing }
    public var progress: Double { requestedUnits > 0 ? min(max(drawnUnits / requestedUnits, 0), 1) : 0 }
}
