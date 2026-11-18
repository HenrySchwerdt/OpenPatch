import Foundation

/// App-side knowledge about one physical pod of the pair. Every pod has its own reservoir, battery and wear state;
/// nothing is shared or averaged. Updated from each status read of THAT pod.
public struct PodRecord: Codable, Equatable {
    public var role: PodRole
    public var size: PodSize
    public var peripheralIdentifier: UUID?
    public var name: String?
    public var reservoirUnits: Double?
    public var batteryFraction: Double?
    public var wearSeconds: UInt32?
    public var isDocked: Bool?
    /// What the pod itself reported last time: is it the active pod?
    public var reportedActive: Bool?
    public var calibration: DriveCalibration?
    public var lastSeen: Date?
    /// Lifecycle phase the app last saw for this pod (initial hint for its transport).
    public var phase: PodPhase = .unpaired
    /// Wire state of THIS pod's command stream: replay protection is per pod, so the sequence number and the history
    /// cursor are stored per pod and never shared.
    public var commandSequence: UInt16 = 1
    public var historyCursor: UInt32?

    public init(role: PodRole, size: PodSize, peripheralIdentifier: UUID? = nil, name: String? = nil) {
        self.role = role; self.size = size; self.peripheralIdentifier = peripheralIdentifier; self.name = name
    }

    public mutating func update(from status: PodStatus, at date: Date) {
        reservoirUnits = status.reservoirUnits
        batteryFraction = Double(status.batteryPercent) / 100
        calibration = status.driveCalibration
        if let pairing = status.pairing {
            wearSeconds = pairing.wearSeconds
            isDocked = pairing.isDocked
            reportedActive = pairing.isActive
        }
        lastSeen = date
        phase = status.phase
    }
}

/// Evidence about the old pod that allows the new pod to be activated.
public enum OldPodSafety: String, Codable, Equatable {
    /// Nothing known: the old pod may still be delivering. Activation of the other pod is FORBIDDEN.
    case unknown
    /// The old pod answered `Release` (or reports released). It cannot deliver.
    case releasedConfirmed
    /// The old pod could not be reached; the user confirmed it was physically removed. A pod that is off the cannula
    /// adapter is undocked, and the undocked hardware gate stops every step even if `Release` never arrived.
    case userConfirmedRemoved
}

public enum SwapPhase: String, Codable, Equatable {
    case idle
    /// `Release(old)` is being sent / outcome unknown. Resend is safe (idempotent).
    case releasingOld
    /// The old pod could not be released (unreachable or rejected). Nothing is activated. The user can retry the
    /// release or confirm that the old pod is physically removed.
    case oldPodUnconfirmed
    /// Old pod safe. Waiting until the new pod reports docked, filled and known calibration.
    case awaitingDock
    /// `Activate(new)` sent, outcome may be unknown. Resolved by a status read or an idempotent resend.
    case activatingNew
    /// New pod active (suspended). Connector prime pending.
    case priming
    /// Prime outcome unknown (lost reply): the user must decide, a blind retry would push more insulin into the connector.
    case primeUncertain
    /// Primed: `Resume` outstanding.
    case resuming
}

/// Persisted state of the pair. Pure value, Codable, changes only through `PairSwapCoordinator`.
public struct PodPairState: Codable, Equatable {
    public var pairID: UInt32
    public var pods: [PodRecord]
    /// The pod the app believes delivers. `nil` during a swap between the release and the activation of the new pod.
    public var active: PodRole?
    public var phase: SwapPhase = .idle
    /// Pod being replaced / pod taking over (valid while `phase != .idle`).
    public var oldRole: PodRole?
    public var newRole: PodRole?
    public var activationID: UInt32 = 0
    public var oldPodSafety: OldPodSafety = .unknown
    public var tempBasalRate: UInt16?
    public var tempBasalEnd: Date?
    public var lastRelease: ReleaseReport?
    public var lastError: String?
    public var nextActivationID: UInt32 = 1

    public init(pairID: UInt32, pods: [PodRecord], active: PodRole? = nil) {
        self.pairID = pairID; self.pods = pods; self.active = active
    }

    public func record(_ role: PodRole) -> PodRecord? { pods.first { $0.role == role } }

    public mutating func update(_ role: PodRole, _ change: (inout PodRecord) -> Void) {
        guard let index = pods.firstIndex(where: { $0.role == role }) else { return }
        change(&pods[index])
    }

    public var spare: PodRole? { active?.other }
    public var isSwapping: Bool { phase != .idle }

    /// Roles for which delivery may currently be possible. At most one, except between a failed `Release` and the
    /// physical removal of that pod (never longer than one swap).
    public var possiblyDelivering: [PodRole] {
        var roles: [PodRole] = []
        if let active { roles.append(active) }
        if phase == .activatingNew || phase == .priming || phase == .primeUncertain || phase == .resuming, let newRole, !roles.contains(newRole) {
            roles.append(newRole)
        }
        if phase == .releasingOld || phase == .oldPodUnconfirmed, let oldRole, oldPodSafety == .unknown, !roles.contains(oldRole) {
            roles.append(oldRole)
        }
        return roles
    }
}

// MARK: Alerts

public enum PairAlert: Equatable {
    case wearWarning(role: PodRole, remaining: TimeInterval)
    case wearExpired(role: PodRole)
    case spareNotReady(role: PodRole, reasons: [SpareProblem])
}

public enum SpareProblem: Equatable {
    case notCharged(batteryFraction: Double)
    case notFilled(reservoirUnits: Double, neededUnits: Double)
    case notSeenRecently
    case unknown
}

public struct PairAlertPolicy {
    /// The spare is checked from this wear time of the active pod on (nominal 48 h minus 12 h to charge and fill).
    public var spareCheckFromWear: TimeInterval = WearPolicy.nominal - 12 * 3600
    public var minimumSpareBattery = 0.5
    /// Units the spare needs for one wear period (priming + `daily * 2`); the caller passes the user's daily need.
    public var minimumSpareReservoir: (PodRecord) -> Double
    public var spareStaleAfter: TimeInterval = 24 * 3600

    public init(dailyInsulinNeed: Double = 40) {
        minimumSpareReservoir = { _ in max(dailyInsulinNeed * 2 + PumpConstants.primeUnits + 5, 20) }
    }

    public func evaluate(_ pair: PodPairState, now: Date) -> [PairAlert] {
        var alerts: [PairAlert] = []
        guard let active = pair.active, let activeRecord = pair.record(active) else { return alerts }
        let wear = TimeInterval(activeRecord.wearSeconds ?? 0)
        if wear >= WearPolicy.stop {
            alerts.append(.wearExpired(role: active))
        } else if wear >= WearPolicy.warning {
            alerts.append(.wearWarning(role: active, remaining: WearPolicy.stop - wear))
        }
        if wear >= spareCheckFromWear, !pair.isSwapping, let spareRecord = pair.record(active.other) {
            let problems = spareProblems(spareRecord, now: now)
            if !problems.isEmpty { alerts.append(.spareNotReady(role: spareRecord.role, reasons: problems)) }
        }
        return alerts
    }

    public func spareProblems(_ spare: PodRecord, now: Date) -> [SpareProblem] {
        guard let seen = spare.lastSeen else { return [.unknown] }
        var problems: [SpareProblem] = []
        if now.timeIntervalSince(seen) > spareStaleAfter { problems.append(.notSeenRecently) }
        if let battery = spare.batteryFraction, battery < minimumSpareBattery { problems.append(.notCharged(batteryFraction: battery)) }
        let needed = minimumSpareReservoir(spare)
        if let reservoir = spare.reservoirUnits, reservoir < needed { problems.append(.notFilled(reservoirUnits: reservoir, neededUnits: needed)) }
        return problems
    }
}
