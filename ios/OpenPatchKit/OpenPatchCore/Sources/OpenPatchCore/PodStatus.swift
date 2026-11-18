import Foundation

public enum FaultCode: UInt8, Equatable, Codable {
    case reservoirEmpty = 1
    case occlusion = 2
    case encoderMismatch = 3
    case motorStall = 4
    case batteryCritical = 5
    case watchdog = 6
    case internalError = 7
    case limitVeto = 8
    case noCalibration = 9     // pod has no valid drive calibration: it can never deliver
    case wearExpired = 10      // 52 h wear limit reached
}

public enum NackReason: UInt8, Equatable {
    case invalidState = 1
    case limitExceeded = 2
    case hourlyLimit = 3
    case busy = 4
    case malformed = 5
    case notConfigured = 6
    case fillOutOfRange = 7
    case unsupported = 8
    case insufficientReservoir = 9
    case session = 10          // authentication / replay / session problems
    case notDocked = 11        // the pod's DOCKED input is off (not on the cannula adapter)
    case released = 12         // the pod is not the active pod of its pair
    case alreadyActive = 13    // activation conflicts with an already active pod / different activation
    case pairMismatch = 14     // pod not paired or pair ID differs
    case charging = 15         // pod sits on a charger
    case calibration = 16      // the pod's drive calibration is missing or unknown
}

public struct BolusStatus: Equatable {
    public var id: UInt16
    public var requestedPulses: UInt16
    public var deliveredPulses: UInt16
    public init(id: UInt16, requestedPulses: UInt16, deliveredPulses: UInt16) {
        self.id = id; self.requestedPulses = requestedPulses; self.deliveredPulses = deliveredPulses
    }
}

public struct TempBasalStatus: Equatable {
    public var rateTicks: UInt16
    public var remainingMinutes: UInt16
    public init(rateTicks: UInt16, remainingMinutes: UInt16) {
        self.rateTicks = rateTicks; self.remainingMinutes = remainingMinutes
    }
    public var unitsPerHour: Double { UnitConversion.units(forPulses: Int(rateTicks)) }
}

public struct PodStatus: Equatable {
    public var phase: PodPhase
    public var reservoirPulses: UInt16
    public var batteryPercent: UInt8
    public var podTime: Date
    public var totalDeliveredPulses: UInt32
    public var bolus: BolusStatus?
    public var tempBasal: TempBasalStatus?
    public var faultCode: FaultCode?
    /// Drive calibration reported by the pod (`DRIVE_CAL`). `nil` = not reported: the app must refuse to operate.
    public var driveCalibration: DriveCalibration?
    /// Pair / dock / wear information (two-pod system). `nil` for pods that do not report it.
    public var pairing: PodPairingInfo?
    /// Only set in the answer to `releasePod`: what the pod delivered since its activation and what is left.
    public var releaseReport: ReleaseReport?

    public init(phase: PodPhase, reservoirPulses: UInt16, batteryPercent: UInt8, podTime: Date,
                totalDeliveredPulses: UInt32, bolus: BolusStatus? = nil, tempBasal: TempBasalStatus? = nil, faultCode: FaultCode? = nil,
                driveCalibration: DriveCalibration? = nil, pairing: PodPairingInfo? = nil, releaseReport: ReleaseReport? = nil) {
        self.driveCalibration = driveCalibration; self.pairing = pairing; self.releaseReport = releaseReport
        self.phase = phase; self.reservoirPulses = reservoirPulses; self.batteryPercent = batteryPercent
        self.podTime = podTime; self.totalDeliveredPulses = totalDeliveredPulses
        self.bolus = bolus; self.tempBasal = tempBasal; self.faultCode = faultCode
    }

    public var reservoirUnits: Double { UnitConversion.units(forPulses: Int(reservoirPulses)) }
    public var totalDeliveredUnits: Double { UnitConversion.units(forPulses: Int(totalDeliveredPulses)) }
}

public enum Response: Equatable {
    case ok(PodStatus)
    case rejected(NackReason)
}

/// Unsolicited pod -> phone notifications.
public enum PodEvent: Equatable {
    case bolusCompleted(id: UInt16, deliveredPulses: UInt16)
    case tempBasalEnded
    case tempBasalRevertedCommLoss
    case lowReservoir(pulses: UInt16)
    case fault(FaultCode)
    case batteryLow(percent: UInt8)
    case primeCompleted
    case docked(Bool)
    case wearWarning
    case wearExpired
    case released(deliveredUnits: Double, reason: ReleaseReason)
}

public enum ReleaseReason: Equatable {
    case command, charger, wear
}
