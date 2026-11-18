import Foundation

/// In-memory pod model. Implements the pod side of the command set with 1-second time resolution so that
/// the app logic, the codec and the lifecycle can be tested end to end without hardware.
/// It mirrors firmware behaviour from spec §7 (limits, hourly cap, comm-loss temp basal fallback).
public final class SimulatedPod {
    public let size: PodSize
    /// What this pod reports as `DRIVE_CAL` (pass an unknown one to the initializer to simulate a wrong drive).
    public let calibration: DriveCalibration
    /// `false` simulates a pod (old firmware) that does not report a calibration at all.
    public var reportsCalibration = true
    public private(set) var phase: PodPhase = .unpaired
    public private(set) var now: Date
    public private(set) var limits = SafetyLimits.default
    public var batteryPercent: UInt8 = 100

    private var utcOffsetMinutes: Int16 = 0
    private var program: BasalProgram?
    private var reservoirSteps = 0
    private(set) var faultCode: FaultCode?
    private var deliveredStepsTotal = 0
    private var events: [PodEvent] = []
    private var lowReservoirAnnounced = false
    private var lastContact: Date

    // Two-pod system (spec §1b). `pairID == 0` = not paired: legacy single-pod behaviour (no activation needed).
    public private(set) var pairID: UInt32 = 0
    public private(set) var role: PodRole?
    public private(set) var isActivated = false
    public private(set) var activationID: UInt32 = 0
    public private(set) var wearSeconds: UInt32 = 0
    /// DOCKED input. A pod that is not docked never delivers (the hardware gate).
    public private(set) var isDocked = true
    public private(set) var isOnCharger = false
    private var wearWarned = false
    private var wearExpired = false
    private var deliveredStepsAtActivation = 0
    private var lastReleaseDeliveredSteps = 0
    private var pendingTemp: HandoverTempBasal?
    private var isStrict: Bool { pairID != 0 }
    private var mayDeliver: Bool { phase == .active && isDocked && (!isStrict || isActivated) && !wearExpired }

    private struct ActiveBolus {
        var id: UInt16
        var requestedPulses: UInt16
        var targetSteps: Int
        var deliveredSteps = 0
        var accumulator: StepAccumulator
    }
    private struct ActiveTemp { var rateTicks: UInt16; var end: Date }

    private var bolus: ActiveBolus?
    private var temp: ActiveTemp?
    private var basalAccumulator: StepAccumulator
    private var primeRemaining: Int = 0
    /// Steps delivered per second for the last hour (ring buffer) -> rolling hourly cap.
    private var hourRing = [Int](repeating: 0, count: 3600)
    private var ringIndex = 0

    public init(size: PodSize, startDate: Date, calibration: DriveCalibration = .zwbpd006006_5_1) {
        self.size = size
        self.now = startDate
        self.lastContact = startDate
        self.calibration = calibration
        self.basalAccumulator = StepAccumulator(calibration: calibration)
    }

    // MARK: Observation

    public var reservoirUnits: Double { UnitConversion.units(forSteps: reservoirSteps, calibration: calibration) }
    public var deliveredUnitsTotal: Double { UnitConversion.units(forSteps: deliveredStepsTotal, calibration: calibration) }
    private var deliveredLastHourUnits: Double { UnitConversion.units(forSteps: hourRing.reduce(0, +), calibration: calibration) }

    public var status: PodStatus {
        let deliveredPulses = UnitConversion.pulses(forUnits: deliveredUnitsTotal)
        return PodStatus(
            phase: phase,
            reservoirPulses: UInt16(clamping: UnitConversion.pulses(forUnits: reservoirUnits)),
            batteryPercent: batteryPercent,
            podTime: now,
            totalDeliveredPulses: UInt32(clamping: deliveredPulses),
            bolus: bolus.map {
                BolusStatus(id: $0.id, requestedPulses: $0.requestedPulses,
                            deliveredPulses: UInt16(clamping: UnitConversion.pulses(forUnits: UnitConversion.units(forSteps: $0.deliveredSteps, calibration: calibration))))
            },
            tempBasal: temp.map { TempBasalStatus(rateTicks: $0.rateTicks, remainingMinutes: UInt16(clamping: Int((max($0.end.timeIntervalSince(now), 0) / 60).rounded(.up)))) },
            faultCode: faultCode,
            driveCalibration: reportsCalibration ? calibration : nil,
            pairing: isStrict ? pairingInfo : nil)
    }

    private var pairingInfo: PodPairingInfo {
        let state: PodDeliveryState = !isActivated ? .released : (wearExpired ? .stoppedWear : (isDocked ? .active : .pausedUndocked))
        return PodPairingInfo(pairID: pairID, role: role, deliveryState: state, isDocked: isDocked, isActive: isActivated,
                              wearSeconds: wearSeconds, wearWarning: isActivated && wearWarned)
    }

    /// The final report of the most recent release.
    public var releaseReport: ReleaseReport {
        ReleaseReport(deliveredSinceActivationUnits: UnitConversion.units(forSteps: lastReleaseDeliveredSteps, calibration: calibration),
                      finalReservoirUnits: reservoirUnits)
    }

    // MARK: Physical world (tests / simulator UI)

    public func setDocked(_ docked: Bool) {
        guard docked != isDocked else { return }
        isDocked = docked
        if !docked { finishBolus(cancelled: true) }   // a bolus is never resumed after an undock
        events.append(.docked(docked))
    }

    /// Placing the pod on a charger forces it to released.
    public func setOnCharger(_ onCharger: Bool) {
        isOnCharger = onCharger
        if onCharger, isActivated { releaseNow(reason: .charger) }
    }

    private func releaseNow(reason: ReleaseReason) {
        finishBolus(cancelled: true)
        temp = nil
        pendingTemp = nil
        lastReleaseDeliveredSteps = max(deliveredStepsTotal - deliveredStepsAtActivation, 0)
        isActivated = false
        transition(.deactivated)
        events.append(.released(deliveredUnits: UnitConversion.units(forSteps: lastReleaseDeliveredSteps, calibration: calibration), reason: reason))
    }

    public func drainEvents() -> [PodEvent] {
        defer { events.removeAll() }
        return events
    }

    // MARK: Commands

    @discardableResult
    public func handle(_ command: Command) -> Response {
        lastContact = now
        // Idempotent re-sends must succeed whatever happened after the first copy (e.g. the app primed already).
        if case .activatePod(let pair, let activation, _, _) = command, isStrict, pair == pairID, isActivated, activation == activationID {
            return .ok(status)
        }
        guard phase.allows(command.kind) else { return .rejected(.invalidState) }
        if let rejection = gate(command.kind) { return .rejected(rejection) }
        switch command {
        case .hello(let version, let time, let offset):
            guard version == PumpConstants.protocolVersion else { return .rejected(.unsupported) }
            now = time; utcOffsetMinutes = offset; lastContact = now
            if phase == .unpaired { phase = .paired }
            else if phase == .deactivated { reset(forRefill: true) }
        case .getStatus, .silenceAlarm:
            break
        case .setTime(let time, let offset):
            now = time; utcOffsetMinutes = offset
        case .setBasalProgram(let newProgram):
            let peak = newProgram.slots.max() ?? 0
            guard UnitConversion.units(forPulses: Int(peak)) <= limits.maxBasalRate + 1e-9 else { return .rejected(.limitExceeded) }
            program = newProgram
        case .setLimits(let newLimits):
            limits = newLimits
        case .confirmFill(let pulses):
            do { try size.validateFill(units: UnitConversion.units(forPulses: Int(pulses))) } catch { return .rejected(.fillOutOfRange) }
            reservoirSteps = UnitConversion.steps(forUnits: UnitConversion.units(forPulses: Int(pulses)), calibration: calibration)
            lowReservoirAnnounced = false
            transition(.fillConfirmed)
        case .prime:
            transition(.primeStarted)
            primeRemaining = Int(PumpConstants.primeDuration)
        case .confirmAttached:
            guard program != nil else { return .rejected(.notConfigured) }
            transition(.attached)
            startPendingTemp()
        case .bolus(let id, let pulses):
            if let rejection = checkBolus(pulses: pulses) { return .rejected(rejection) }
            bolus = ActiveBolus(id: id, requestedPulses: pulses, targetSteps: UnitConversion.steps(forUnits: UnitConversion.units(forPulses: Int(pulses)), calibration: calibration),
                                accumulator: StepAccumulator(calibration: calibration))
        case .cancelBolus:
            finishBolus(cancelled: true)
        case .setTempBasal(let ticks, let minutes):
            guard minutes > 0, TimeInterval(minutes) * 60 <= PumpConstants.maxTempBasalDuration else { return .rejected(.malformed) }
            guard UnitConversion.units(forPulses: Int(ticks)) <= limits.maxBasalRate + 1e-9 else { return .rejected(.limitExceeded) }
            temp = ActiveTemp(rateTicks: ticks, end: now.addingTimeInterval(TimeInterval(minutes) * 60))
        case .cancelTempBasal:
            temp = nil
        case .suspend:
            finishBolus(cancelled: true)
            if temp != nil { temp = nil; events.append(.tempBasalEnded) }
            transition(.suspended)
        case .resume:
            transition(.resumed)
            startPendingTemp()
        case .deactivate:
            finishBolus(cancelled: true)
            temp = nil
            transition(.deactivated)
        case .setPairing(let pair, let newRole):
            guard !isActivated else { return .rejected(.alreadyActive) }
            guard pair != 0 else { return .rejected(.malformed) }
            pairID = pair; role = newRole
        case .activatePod(let pair, let activation, let newProgram, let handover):
            guard isStrict, pair == pairID else { return .rejected(.pairMismatch) }
            guard !isActivated else { return .rejected(.alreadyActive) }
            guard activation != 0 else { return .rejected(.malformed) }
            guard !isOnCharger else { return .rejected(.charging) }
            guard isDocked else { return .rejected(.notDocked) }
            let peak = newProgram.slots.max() ?? 0
            guard UnitConversion.units(forPulses: Int(peak)) <= limits.maxBasalRate + 1e-9 else { return .rejected(.limitExceeded) }
            if let handover, handover.remainingMinutes > 0 {
                guard UnitConversion.units(forPulses: Int(handover.rateTicks)) <= limits.maxBasalRate + 1e-9 else { return .rejected(.limitExceeded) }
            }
            program = newProgram
            pendingTemp = handover.flatMap { $0.remainingMinutes > 0 ? $0 : nil }
            isActivated = true
            activationID = activation
            wearSeconds = 0; wearWarned = false; wearExpired = false
            if faultCode == .wearExpired { faultCode = nil }
            deliveredStepsAtActivation = deliveredStepsTotal
        case .releasePod(let pair):
            guard isStrict, pair == pairID else { return .rejected(.pairMismatch) }
            if isActivated { releaseNow(reason: .command) }
            var answer = status
            answer.releaseReport = releaseReport
            return .ok(answer)
        }
        return .ok(status)
    }

    /// Hardware / pairing preconditions the pod enforces on top of the lifecycle.
    private func gate(_ kind: CommandKind) -> NackReason? {
        switch kind {
        case .bolus, .resume, .confirmAttached, .prime:
            if isStrict && !isActivated { return .released }
            if !isDocked { return .notDocked }
        case .setTempBasal:
            if isStrict && !isActivated { return .released }
        default: break
        }
        return nil
    }

    private func checkBolus(pulses: UInt16) -> NackReason? {
        guard bolus == nil else { return .busy }
        guard pulses > 0 else { return .malformed }
        let units = UnitConversion.units(forPulses: Int(pulses))
        guard (try? limits.validateBolus(units: units)) != nil else { return .limitExceeded }
        guard (try? limits.validateHourly(requested: units, alreadyDelivered: deliveredLastHourUnits)) != nil else { return .hourlyLimit }
        guard UnitConversion.steps(forUnits: units, calibration: calibration) <= reservoirSteps else { return .insufficientReservoir }
        return nil
    }

    private func startPendingTemp() {
        guard phase == .active, let handover = pendingTemp else { return }
        pendingTemp = nil
        temp = ActiveTemp(rateTicks: handover.rateTicks, end: now.addingTimeInterval(TimeInterval(handover.remainingMinutes) * 60))
    }

    private func transition(_ event: LifecycleEvent) {
        if let next = PodLifecycle.transition(from: phase, event: event) { phase = next }
    }

    private func reset(forRefill: Bool) {
        _ = PodLifecycle.transition(from: phase, event: .refillRequested).map { phase = $0 }
        reservoirSteps = 0
        faultCode = nil
        program = forRefill ? program : nil
    }

    // MARK: Fault injection

    public func injectFault(_ code: FaultCode) { enterFault(code) }

    private func enterFault(_ code: FaultCode) {
        guard phase != .faulted else { return }
        finishBolus(cancelled: true)
        temp = nil
        faultCode = code
        transition(.faulted)
        events.append(.fault(code))
    }

    private func finishBolus(cancelled: Bool) {
        guard let current = bolus else { return }
        let deliveredUnits = UnitConversion.units(forSteps: current.deliveredSteps, calibration: calibration)
        let pulses = cancelled ? UInt16(clamping: UnitConversion.pulses(forUnits: deliveredUnits)) : current.requestedPulses
        events.append(.bolusCompleted(id: current.id, deliveredPulses: pulses))
        bolus = nil
    }

    // MARK: Time

    public func advance(by seconds: Int) {
        for _ in 0..<max(seconds, 0) { tick() }
    }

    private func tick() {
        var stepsThisSecond = 0

        if phase == .priming {
            primeRemaining -= 1
            if primeRemaining <= 0 {
                reservoirSteps = max(reservoirSteps - UnitConversion.steps(forUnits: PumpConstants.primeUnits, calibration: calibration), 0)
                transition(.primeCompleted)
                events.append(.primeCompleted)
            }
        }

        if isActivated, !wearExpired { tickWear() }
        if mayDeliver {
            stepsThisSecond += deliverBolusSecond()
            stepsThisSecond += deliverBasalSecond()
        }

        reservoirSteps -= stepsThisSecond
        deliveredStepsTotal += stepsThisSecond
        hourRing[ringIndex] = stepsThisSecond
        ringIndex = (ringIndex + 1) % hourRing.count
        now.addTimeInterval(1)

        if reservoirSteps <= 0 && phase == .active {
            reservoirSteps = 0
            enterFault(.reservoirEmpty)
        } else if !lowReservoirAnnounced, phase == .active, reservoirUnits < PumpConstants.lowReservoirUnits {
            lowReservoirAnnounced = true
            events.append(.lowReservoir(pulses: UInt16(clamping: UnitConversion.pulses(forUnits: reservoirUnits))))
        }
        expireTempBasalIfNeeded()
    }

    private func tickWear() {
        wearSeconds += 1
        if !wearWarned, TimeInterval(wearSeconds) >= WearPolicy.warning {
            wearWarned = true
            events.append(.wearWarning)
        }
        if TimeInterval(wearSeconds) >= WearPolicy.stop {
            wearExpired = true
            events.append(.wearExpired)
            enterFault(.wearExpired)
        }
    }

    private func deliverBolusSecond() -> Int {
        guard var current = bolus else { return 0 }
        let wanted = current.accumulator.steps(forUnits: limits.bolusUnitsPerMinute / 60)
        let steps = min(wanted, current.targetSteps - current.deliveredSteps, reservoirSteps)
        current.deliveredSteps += steps
        bolus = current
        if current.deliveredSteps >= current.targetSteps { finishBolus(cancelled: false) }
        return steps
    }

    private func currentBasalRate() -> Double {
        if let temp { return UnitConversion.units(forPulses: Int(temp.rateTicks)) }
        guard let program else { return 0 }
        let local = Int(now.timeIntervalSince1970) + Int(utcOffsetMinutes) * 60
        return program.unitsPerHour(atOffset: TimeInterval(((local % 86_400) + 86_400) % 86_400))
    }

    private func deliverBasalSecond() -> Int {
        let steps = basalAccumulator.steps(forUnits: currentBasalRate() / 3600)
        return min(steps, max(reservoirSteps, 0))
    }

    private func expireTempBasalIfNeeded() {
        guard let current = temp else { return }
        if now >= current.end {
            temp = nil
            events.append(.tempBasalEnded)
        } else if now.timeIntervalSince(lastContact) > limits.commLossTempBasalLimit {
            temp = nil
            events.append(.tempBasalRevertedCommLoss)
        }
    }
}
