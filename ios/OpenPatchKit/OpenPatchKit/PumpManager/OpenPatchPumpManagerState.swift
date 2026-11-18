import Foundation
import LoopKit
import OpenPatchCore

/// Everything the manager persists. Codable -> JSON blob inside `rawState` (keeps the plist-compatible
/// `RawStateValue` dictionary small and migratable).
public struct OpenPatchPumpManagerState: RawRepresentable, Equatable {
    public typealias RawValue = PumpManager.RawStateValue
    public static let currentVersion = 1

    // Pairing / identity
    public var podSize: PodSize = .u200
    public var peripheralIdentifier: UUID?
    public var podName: String?
    public var usesSimulatedPod = false
    public var firmwareVersion: String?
    /// Two-pod system: both pods, which one is active, the swap state machine. `nil` before the first pod is paired.
    public var pair: PodPairState?
    /// Role of the pod `PumpManager.transport` talks to (the active pod once setup finished).
    public var podRole: PodRole?
    /// Drive calibration reported by that pod in its last status, and whether it is acceptable.
    /// Without a known calibration the manager refuses to deliver, prime or fill.
    public var driveCalibration: DriveCalibration?
    public var calibrationProblem: CalibrationProblem?
    /// What the pod itself says about being the active pod (`nil`: pod does not report it).
    public var podReportsActive: Bool?

    // Lifecycle
    public var phase: PodPhase = .unpaired
    public var faultCode: FaultCode?
    public var isSetupCompleted = false
    public var activatedAt: Date?

    // Telemetry
    public var reservoirUnits: Double?
    public var batteryFraction: Double?
    public var lastSync: Date?
    public var lastPodTotalDeliveredUnits: Double?

    // Therapy settings
    public var basalSegments: [BasalSegment] = []
    public var maxBolus = SafetyLimits.defaultMaxBolus
    public var maxBasalRate = SafetyLimits.defaultMaxBasalRate
    public var insulinType: InsulinType?
    public var timeZoneIdentifier = TimeZone.current.identifier

    // Delivery
    public var suspendedAt: Date?
    public var resumedAt: Date?
    public var nextBolusID: UInt16 = 1
    public var deliveryUncertainSince: Date?
    /// Wire protocol: next command sequence number (replay protection on the pod requires strictly increasing values).
    public var commandSequence: UInt16 = 1
    /// Wire protocol: ID of the next pod history event to fetch (everything below was delivered).
    public var historyCursor: UInt32?
    var unfinalizedBolus: OpenPatchDose?
    var unfinalizedTempBasal: OpenPatchDose?
    /// Finished doses not yet confirmed as reported to the host (replayed on next sync).
    var unreportedFinishedDoses: [OpenPatchDose] = []

    public init() {}

    public var timeZone: TimeZone { TimeZone(identifier: timeZoneIdentifier) ?? .current }
    public var safetyLimits: SafetyLimits { SafetyLimits(maxBolus: maxBolus, maxBasalRate: maxBasalRate) }
    public var isSuspended: Bool { phase == .suspended }
    public var isSwapping: Bool { pair?.isSwapping ?? false }

    /// `nil` = delivery-related commands are allowed. Anything else must stop priming, filling and delivery.
    public var calibrationBlock: OpenPatchError? {
        if let problem = calibrationProblem { return .calibration(problem) }
        guard let cal = driveCalibration, cal.isKnown else { return .calibration(.missing) }
        return nil
    }

    public var basalProgram: BasalProgram? {
        guard !basalSegments.isEmpty else { return nil }
        return try? BasalProgram(segments: basalSegments, limits: safetyLimits)
    }

    // MARK: RawRepresentable

    private struct Stored: Codable {
        var podSize: PodSize
        var peripheralIdentifier: UUID?
        var podName: String?
        var usesSimulatedPod: Bool
        var firmwareVersion: String?
        var pair: PodPairState?
        var podRole: PodRole?
        var driveCalibration: DriveCalibration?
        var calibrationProblem: CalibrationProblem?
        var podReportsActive: Bool?
        var phase: PodPhase
        var faultCode: FaultCode?
        var isSetupCompleted: Bool
        var activatedAt: Date?
        var reservoirUnits: Double?
        var batteryFraction: Double?
        var lastSync: Date?
        var lastPodTotalDeliveredUnits: Double?
        var basalSegments: [BasalSegment]
        var maxBolus: Double
        var maxBasalRate: Double
        var insulinType: InsulinType?
        var timeZoneIdentifier: String
        var suspendedAt: Date?
        var resumedAt: Date?
        var nextBolusID: UInt16
        var deliveryUncertainSince: Date?
        var commandSequence: UInt16?
        var historyCursor: UInt32?
        var unfinalizedBolus: OpenPatchDose?
        var unfinalizedTempBasal: OpenPatchDose?
        var unreportedFinishedDoses: [OpenPatchDose]
    }

    public init?(rawValue: RawValue) {
        guard let version = rawValue["version"] as? Int, version <= Self.currentVersion,
              let data = rawValue["state"] as? Data,
              let s = try? JSONDecoder().decode(Stored.self, from: data) else { return nil }
        podSize = s.podSize; peripheralIdentifier = s.peripheralIdentifier; podName = s.podName
        usesSimulatedPod = s.usesSimulatedPod; firmwareVersion = s.firmwareVersion
        pair = s.pair; podRole = s.podRole; driveCalibration = s.driveCalibration
        calibrationProblem = s.calibrationProblem; podReportsActive = s.podReportsActive
        phase = s.phase; faultCode = s.faultCode; isSetupCompleted = s.isSetupCompleted; activatedAt = s.activatedAt
        reservoirUnits = s.reservoirUnits; batteryFraction = s.batteryFraction; lastSync = s.lastSync
        lastPodTotalDeliveredUnits = s.lastPodTotalDeliveredUnits
        basalSegments = s.basalSegments; maxBolus = s.maxBolus; maxBasalRate = s.maxBasalRate
        insulinType = s.insulinType; timeZoneIdentifier = s.timeZoneIdentifier
        suspendedAt = s.suspendedAt; resumedAt = s.resumedAt; nextBolusID = s.nextBolusID
        deliveryUncertainSince = s.deliveryUncertainSince
        commandSequence = s.commandSequence ?? 1
        historyCursor = s.historyCursor
        unfinalizedBolus = s.unfinalizedBolus; unfinalizedTempBasal = s.unfinalizedTempBasal
        unreportedFinishedDoses = s.unreportedFinishedDoses
    }

    public var rawValue: RawValue {
        let s = Stored(podSize: podSize, peripheralIdentifier: peripheralIdentifier, podName: podName,
                       usesSimulatedPod: usesSimulatedPod, firmwareVersion: firmwareVersion, pair: pair, podRole: podRole,
                       driveCalibration: driveCalibration, calibrationProblem: calibrationProblem,
                       podReportsActive: podReportsActive, phase: phase,
                       faultCode: faultCode, isSetupCompleted: isSetupCompleted, activatedAt: activatedAt,
                       reservoirUnits: reservoirUnits, batteryFraction: batteryFraction, lastSync: lastSync,
                       lastPodTotalDeliveredUnits: lastPodTotalDeliveredUnits, basalSegments: basalSegments,
                       maxBolus: maxBolus, maxBasalRate: maxBasalRate, insulinType: insulinType,
                       timeZoneIdentifier: timeZoneIdentifier, suspendedAt: suspendedAt, resumedAt: resumedAt,
                       nextBolusID: nextBolusID, deliveryUncertainSince: deliveryUncertainSince,
                       commandSequence: commandSequence, historyCursor: historyCursor,
                       unfinalizedBolus: unfinalizedBolus, unfinalizedTempBasal: unfinalizedTempBasal,
                       unreportedFinishedDoses: unreportedFinishedDoses)
        let data = (try? JSONEncoder().encode(s)) ?? Data()
        return ["version": Self.currentVersion, "state": data]
    }
}

extension OpenPatchPumpManagerState: CustomDebugStringConvertible {
    public var debugDescription: String {
        """
        ## OpenPatchPumpManagerState
        phase: \(phase) fault: \(String(describing: faultCode)) size: \(podSize.displayName)
        reservoir: \(String(describing: reservoirUnits)) battery: \(String(describing: batteryFraction))
        lastSync: \(String(describing: lastSync)) uncertain: \(String(describing: deliveryUncertainSince))
        bolus: \(String(describing: unfinalizedBolus)) temp: \(String(describing: unfinalizedTempBasal))
        """
    }
}
