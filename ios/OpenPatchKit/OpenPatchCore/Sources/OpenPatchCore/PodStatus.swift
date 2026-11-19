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
    case selfTestRefused = 17  // not suspended, a draw or another self-test is running
    case latched = 18          // a latched diagnostic code refuses Resume / Activate until its verification test passes
    case notClearable = 19     // ClearDiag: latched and not verified, or the cause persists
    case noSchedule = 20       // Resume refused: the pod holds no basal schedule (e.g. not restorable after a reset)
    case primeRequired = 21    // a fill / draw was not followed by a prime yet
    case podDocked = 22        // the fill needs an undocked pod (a docked pod is connected to the cannula and never retracts)
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
    /// Diagnostics (`DIAG_SUMMARY`, `FRU_HEALTH`, `POD_UID`). `nil` = a v1 pod without diagnostics: `faultCode` stays the only summary.
    public var diag: DiagSummary?
    public var fruHealth: FruHealth?
    public var uid: PodUID?
    /// Fill / draw job of the pod (`DRAW_STATE` ...). `nil` = the pod does not report it (C reference, simulator).
    public var fill: FillStatus?
    /// `NEXT_EVENT_ID` of the pod's history (`nil` = no history, e.g. the simulator): "caught up" means the cursor reached it.
    public var historyNextEventID: UInt32?

    public init(phase: PodPhase, reservoirPulses: UInt16, batteryPercent: UInt8, podTime: Date,
                totalDeliveredPulses: UInt32, bolus: BolusStatus? = nil, tempBasal: TempBasalStatus? = nil, faultCode: FaultCode? = nil,
                driveCalibration: DriveCalibration? = nil, pairing: PodPairingInfo? = nil, releaseReport: ReleaseReport? = nil,
                diag: DiagSummary? = nil, fruHealth: FruHealth? = nil, uid: PodUID? = nil, fill: FillStatus? = nil, historyNextEventID: UInt32? = nil) {
        self.fill = fill; self.historyNextEventID = historyNextEventID
        self.driveCalibration = driveCalibration; self.pairing = pairing; self.releaseReport = releaseReport
        self.diag = diag; self.fruHealth = fruHealth; self.uid = uid
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
    /// The pod logged the start of a bolus of `pulses` x 0.05 U. Arrives from the history, also when the reply of the
    /// bolus command was lost: the proof that the pod executed it.
    case bolusStarted(pulses: UInt16)
    /// The pod logged the start of a temp basal (same purpose as `bolusStarted`).
    case tempBasalStarted(rateTicks: UInt16, durationMinutes: UInt16)
    /// Fill / draw progress or end (notification or history): what the pod confirmed so far.
    case fillUpdate(state: FillState, drawnUnits: Double)
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
    /// A diagnostic record was raised (or an old one found by the pull path). The root cause rule is applied by the consumer.
    case diag(DiagRecord)
    /// A diagnostic condition cleared.
    case diagCleared(DiagCode)
    /// Self-test progress (bit masks of the steps).
    case selfTest(passed: UInt16, failed: UInt16)
}

public enum ReleaseReason: Equatable {
    case command, charger, wear
}
