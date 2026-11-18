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

    public init(phase: PodPhase, reservoirPulses: UInt16, batteryPercent: UInt8, podTime: Date,
                totalDeliveredPulses: UInt32, bolus: BolusStatus? = nil, tempBasal: TempBasalStatus? = nil, faultCode: FaultCode? = nil) {
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
}
