import Foundation

/// In-memory pod model. Implements the pod side of the command set with 1-second time resolution so that
/// the app logic, the codec and the lifecycle can be tested end to end without hardware.
/// It mirrors firmware behaviour from spec §7 (limits, hourly cap, comm-loss temp basal fallback).
public final class SimulatedPod {
    public let size: PodSize
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

    private struct ActiveBolus {
        var id: UInt16
        var requestedPulses: UInt16
        var targetSteps: Int
        var deliveredSteps = 0
        var accumulator = StepAccumulator()
    }
    private struct ActiveTemp { var rateTicks: UInt16; var end: Date }

    private var bolus: ActiveBolus?
    private var temp: ActiveTemp?
    private var basalAccumulator = StepAccumulator()
    private var primeRemaining: Int = 0
    /// Steps delivered per second for the last hour (ring buffer) -> rolling hourly cap.
    private var hourRing = [Int](repeating: 0, count: 3600)
    private var ringIndex = 0

    public init(size: PodSize, startDate: Date) {
        self.size = size
        self.now = startDate
        self.lastContact = startDate
    }

    // MARK: Observation

    public var reservoirUnits: Double { UnitConversion.units(forSteps: reservoirSteps) }
    public var deliveredUnitsTotal: Double { UnitConversion.units(forSteps: deliveredStepsTotal) }
    private var deliveredLastHourUnits: Double { UnitConversion.units(forSteps: hourRing.reduce(0, +)) }

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
                            deliveredPulses: UInt16(clamping: UnitConversion.pulses(forUnits: UnitConversion.units(forSteps: $0.deliveredSteps))))
            },
            tempBasal: temp.map { TempBasalStatus(rateTicks: $0.rateTicks, remainingMinutes: UInt16(clamping: Int((max($0.end.timeIntervalSince(now), 0) / 60).rounded(.up)))) },
            faultCode: faultCode)
    }

    public func drainEvents() -> [PodEvent] {
        defer { events.removeAll() }
        return events
    }

    // MARK: Commands

    @discardableResult
    public func handle(_ command: Command) -> Response {
        lastContact = now
        guard phase.allows(command.kind) else { return .rejected(.invalidState) }
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
            reservoirSteps = UnitConversion.steps(forUnits: UnitConversion.units(forPulses: Int(pulses)))
            lowReservoirAnnounced = false
            transition(.fillConfirmed)
        case .prime:
            transition(.primeStarted)
            primeRemaining = Int(PumpConstants.primeDuration)
        case .confirmAttached:
            guard program != nil else { return .rejected(.notConfigured) }
            transition(.attached)
        case .bolus(let id, let pulses):
            if let rejection = checkBolus(pulses: pulses) { return .rejected(rejection) }
            bolus = ActiveBolus(id: id, requestedPulses: pulses, targetSteps: UnitConversion.steps(forUnits: UnitConversion.units(forPulses: Int(pulses))))
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
        case .deactivate:
            finishBolus(cancelled: true)
            temp = nil
            transition(.deactivated)
        }
        return .ok(status)
    }

    private func checkBolus(pulses: UInt16) -> NackReason? {
        guard bolus == nil else { return .busy }
        guard pulses > 0 else { return .malformed }
        let units = UnitConversion.units(forPulses: Int(pulses))
        guard (try? limits.validateBolus(units: units)) != nil else { return .limitExceeded }
        guard (try? limits.validateHourly(requested: units, alreadyDelivered: deliveredLastHourUnits)) != nil else { return .hourlyLimit }
        guard UnitConversion.steps(forUnits: units) <= reservoirSteps else { return .insufficientReservoir }
        return nil
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
        let deliveredUnits = UnitConversion.units(forSteps: current.deliveredSteps)
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
                reservoirSteps = max(reservoirSteps - UnitConversion.steps(forUnits: PumpConstants.primeUnits), 0)
                transition(.primeCompleted)
                events.append(.primeCompleted)
            }
        }

        if phase == .active {
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
