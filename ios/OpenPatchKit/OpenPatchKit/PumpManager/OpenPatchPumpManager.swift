import Foundation
import HealthKit
import LoopKit
import OpenPatchCore

/// LoopKit `PumpManager` for the OpenPatch DIY patch pump (EXPERIMENTAL, not a medical device).
///
/// Threading: `state` is guarded by `lock`; delegate callbacks go through `WeakSynchronizedDelegate` on
/// `delegateQueue`. Transport callbacks may arrive on any queue and only touch state through `mutateState`.
public final class OpenPatchPumpManager: PumpManager {
    public static let pluginIdentifier = "OpenPatch"
    public static let localizedTitle = "OpenPatch"
    public var localizedTitle: String { Self.localizedTitle }

    // MARK: Static capabilities (readable before a pump exists, used by Trio onboarding)

    public static var onboardingMaximumBasalScheduleEntryCount: Int { PumpConstants.maxBasalSegments }
    public static var onboardingSupportedBasalRates: [Double] {
        UnitConversion.supportedVolumes(maximum: SafetyLimits.absoluteMaxBasalRate)
    }
    public static var onboardingSupportedBolusVolumes: [Double] {
        UnitConversion.supportedVolumes(maximum: SafetyLimits.absoluteMaxBolus)
    }
    public static var onboardingSupportedMaximumBolusVolumes: [Double] { onboardingSupportedBolusVolumes }

    // MARK: Dependencies / storage

    /// Override in tests / the iOS simulator to inject `SimulatedTransport`.
    public static var transportFactory: (OpenPatchPumpManagerState) -> OpenPatchTransport = { state in
        state.usesSimulatedPod
            ? OpenPatchSimulator.shared.makeTransport(size: state.podSize)
            : makeV1Transport(state: state, link: CoreBluetoothLink(peripheralIdentifier: state.peripheralIdentifier))
    }

    /// Transport of ONE pod of the pair (A or B). Tests inject `SimulatedTransport`s here.
    public static var pairTransportFactory: (OpenPatchPumpManagerState, PodRole) -> OpenPatchTransport = { state, role in
        state.usesSimulatedPod
            ? OpenPatchSimulator.shared.makeTransport(size: state.podSize, role: role)
            : makeV1Transport(state: state, link: CoreBluetoothLink(peripheralIdentifier: state.peripheralIdentifier))
    }

    /// The persisted `commandSequence` is written asynchronously by the host, so after a crash it can lag by a few
    /// commands. The pod accepts gaps, so restore with a safety margin instead of risking a replayed `seq`.
    static let sequenceRestoreMargin: UInt16 = 16

    public static func makeV1Transport(state: OpenPatchPumpManagerState, link: FrameLink) -> V1Transport {
        let restored = state.commandSequence == 1 && state.historyCursor == nil
            ? UInt16(1) : UInt16(min(Int(state.commandSequence) + Int(sequenceRestoreMargin), 0xFFFE))
        return V1Transport(link: link, initialPhase: state.phase, initialSequence: restored, initialHistoryCursor: state.historyCursor)
    }

    /// Hooks transport events and checkpoints (sequence, history cursor) into the persisted state.
    func wire(_ transport: OpenPatchTransport, role: PodRole? = nil) {
        guard let role else {
            transport.eventHandler = { [weak self] event in self?.handle(event: event) }
            (transport as? V1Transport)?.checkpointHandler = { [weak self] checkpoint in
                self?.mutateState {
                    $0.commandSequence = max($0.commandSequence, checkpoint.nextSequence)
                    $0.historyCursor = checkpoint.historyCursor ?? $0.historyCursor
                }
            }
            return
        }
        // Pair mode: events of the active pod drive the delivery state, events of the other pod must not.
        transport.eventHandler = { [weak self] event in
            guard let self else { return }
            if role == self.state.podRole { self.handle(event: event) } else { self.handleSparePodEvent(event, from: role) }
        }
        (transport as? V1Transport)?.checkpointHandler = { [weak self] checkpoint in
            // Replay protection is per pod: its own sequence number and history cursor live in ITS record.
            self?.mutateState { st in
                st.pair?.update(role) {
                    $0.commandSequence = max($0.commandSequence, checkpoint.nextSequence)
                    $0.historyCursor = checkpoint.historyCursor ?? $0.historyCursor
                }
                if role == st.podRole {
                    st.commandSequence = max(st.commandSequence, checkpoint.nextSequence)
                    st.historyCursor = checkpoint.historyCursor ?? st.historyCursor
                }
            }
        }
    }

    let lock = NSLock()
    private var _state: OpenPatchPumpManagerState
    var transport: OpenPatchTransport
    let delegate = WeakSynchronizedDelegate<PumpManagerDelegate>()
    private let statusObservers = WeakSynchronizedSet<PumpManagerStatusObserver>()
    private var transientBasalState: PumpManagerStatus.BasalDeliveryState?
    private var transientBolusState: PumpManagerStatus.BolusState?
    var finalizationItem: DispatchWorkItem?
    /// Pair mode: one transport per pod (the active pod's is `transport`), the swap state machine, alerts already raised.
    var pairTransports: [PodRole: OpenPatchTransport] = [:]
    var swapCoordinator: PairSwapCoordinator?
    var raisedPairAlerts = Set<String>()
    /// Set by a swap: the next status may carry a temp basal handed over from the old pod, which this manager must adopt.
    var adoptTempBasalFromNextStatus = false
    /// Most recently finalized bolus (any path), so `cancelBolus` can report it even if the pod event arrived first.
    var lastFinalizedBolus: OpenPatchDose?
    let workQueue = DispatchQueue(label: "org.openpatch.pumpmanager")

    public var state: OpenPatchPumpManagerState {
        lock.lock(); defer { lock.unlock() }
        return _state
    }

    // MARK: Init

    public init(state: OpenPatchPumpManagerState = OpenPatchPumpManagerState(), transport: OpenPatchTransport? = nil) {
        _state = state
        self.transport = transport ?? Self.transportFactory(state)
        wire(self.transport)
        configurePair()
        scheduleFinalization()
    }

    public convenience init?(rawState: RawStateValue) {
        guard let state = OpenPatchPumpManagerState(rawValue: rawState) else { return nil }
        self.init(state: state)
    }

    public var rawState: RawStateValue { state.rawValue }
    public var isOnboarded: Bool { state.isSetupCompleted }

    /// Replaces the transport (after pairing a new peripheral).
    func replaceTransport(_ newTransport: OpenPatchTransport) {
        transport.disconnect()
        transport = newTransport
        wire(newTransport)
    }

    // MARK: State mutation & notification

    func mutateState(_ change: (inout OpenPatchPumpManagerState) -> Void) {
        lock.lock()
        let old = _state
        var new = old
        change(&new)
        _state = new
        let basalT = transientBasalState, bolusT = transientBolusState
        lock.unlock()
        guard new != old else { return }
        notify(oldStatus: makeStatus(old, basalT, bolusT), newStatus: makeStatus(new, basalT, bolusT))
    }

    private func setTransient(basal: PumpManagerStatus.BasalDeliveryState?? = nil, bolus: PumpManagerStatus.BolusState?? = nil) {
        lock.lock()
        let current = _state
        let oldStatus = makeStatus(current, transientBasalState, transientBolusState)
        if let basal { transientBasalState = basal }
        if let bolus { transientBolusState = bolus }
        let newStatus = makeStatus(current, transientBasalState, transientBolusState)
        lock.unlock()
        if oldStatus != newStatus { notify(oldStatus: oldStatus, newStatus: newStatus, stateChanged: false) }
    }

    private func notify(oldStatus: PumpManagerStatus, newStatus: PumpManagerStatus, stateChanged: Bool = true) {
        delegate.notify { delegate in
            if stateChanged { delegate?.pumpManagerDidUpdateState(self) }
            if oldStatus != newStatus { delegate?.pumpManager(self, didUpdate: newStatus, oldStatus: oldStatus) }
        }
        if oldStatus != newStatus {
            statusObservers.forEach { $0.pumpManager(self, didUpdate: newStatus, oldStatus: oldStatus) }
        }
    }

    // MARK: PumpManager - basic properties

    public var delegateQueue: DispatchQueue! {
        get { delegate.queue }
        set { delegate.queue = newValue }
    }

    public var pumpManagerDelegate: PumpManagerDelegate? {
        get { delegate.delegate }
        set { delegate.delegate = newValue }
    }

    /// Rounds down on the 0.05 U grid but, unlike the protocol default, does not clamp to the maximum bolus:
    /// an over-limit request must fail loudly in `enactBolus` instead of being silently shortened.
    public func roundToSupportedBolusVolume(units: Double) -> Double {
        UnitConversion.roundDownToPulse(units)
    }

    public var supportedBasalRates: [Double] { UnitConversion.supportedVolumes(maximum: state.maxBasalRate) }
    public var supportedBolusVolumes: [Double] { UnitConversion.supportedVolumes(maximum: state.maxBolus) }
    public var supportedMaximumBolusVolumes: [Double] { Self.onboardingSupportedMaximumBolusVolumes }
    public var maximumBasalScheduleEntryCount: Int { PumpConstants.maxBasalSegments }
    public var minimumBasalScheduleEntryDuration: TimeInterval { PumpConstants.basalSlotDuration }
    public var pumpRecordsBasalProfileStartEvents: Bool { false }
    public var pumpReservoirCapacity: Double { state.podSize.capacityUnits }
    public var lastSync: Date? { state.lastSync }
    public var status: PumpManagerStatus {
        lock.lock(); defer { lock.unlock() }
        return makeStatus(_state, transientBasalState, transientBolusState)
    }

    private func device(_ state: OpenPatchPumpManagerState) -> HKDevice {
        HKDevice(name: Self.pluginIdentifier, manufacturer: "OpenPatch DIY (experimental)", model: state.podSize.displayName,
                 hardwareVersion: nil, firmwareVersion: state.firmwareVersion, softwareVersion: "0.1",
                 localIdentifier: state.peripheralIdentifier?.uuidString, udiDeviceIdentifier: nil)
    }

    func makeStatus(_ state: OpenPatchPumpManagerState,
                    _ basalTransient: PumpManagerStatus.BasalDeliveryState?,
                    _ bolusTransient: PumpManagerStatus.BolusState?,
                    now: Date = Date()) -> PumpManagerStatus {
        PumpManagerStatus(timeZone: state.timeZone,
                          device: device(state),
                          pumpBatteryChargeRemaining: state.batteryFraction,
                          basalDeliveryState: basalTransient ?? basalDeliveryState(for: state, now: now),
                          bolusState: bolusTransient ?? bolusState(for: state, now: now),
                          insulinType: state.insulinType,
                          deliveryIsUncertain: state.deliveryUncertainSince != nil)
    }

    private func basalDeliveryState(for state: OpenPatchPumpManagerState, now: Date) -> PumpManagerStatus.BasalDeliveryState? {
        switch state.phase {
        case .suspended:
            return .suspended(state.suspendedAt ?? now)
        case .active:
            if let temp = state.unfinalizedTempBasal, !temp.isFinished(at: now) {
                return .tempBasal(temp.doseEntry(isMutable: true, at: now))
            }
            return .active(state.resumedAt ?? state.activatedAt ?? now)
        default:
            return nil
        }
    }

    private func bolusState(for state: OpenPatchPumpManagerState, now: Date) -> PumpManagerStatus.BolusState {
        if let bolus = state.unfinalizedBolus, !bolus.isFinished(at: now) {
            return .inProgress(bolus.doseEntry(isMutable: true, at: now))
        }
        return .noBolus
    }

    // MARK: Observers / heartbeat

    public func addStatusObserver(_ observer: PumpManagerStatusObserver, queue: DispatchQueue) {
        statusObservers.insert(observer, queue: queue)
    }

    public func removeStatusObserver(_ observer: PumpManagerStatusObserver) {
        statusObservers.removeElement(observer)
    }

    /// The pod keeps its own BLE link alive (CoreBluetooth background mode); Trio is woken by the CGM.
    public func setMustProvideBLEHeartbeat(_ mustProvideBLEHeartbeat: Bool) {}

    public func ensureCurrentPumpData(completion: ((Date?) -> Void)?) {
        guard state.phase != .unpaired, state.isSetupCompleted else { completion?(state.lastSync); return }
        guard !state.isSwapping else { completion?(state.lastSync); return }   // the swap owns the radio
        send(.getStatus) { [weak self] result in
            guard let self else { return }
            if case .failure(let failure) = result {
                self.log("sync failed: \(failure.error)")
            }
            self.refreshSparePodIfStale()
            self.evaluatePairAlerts()
            completion?(self.state.lastSync)
        }
    }

    // MARK: Bolus

    public func estimatedDuration(toBolus units: Double) -> TimeInterval {
        UnitConversion.bolusDuration(forUnits: units)
    }

    public func createBolusProgressReporter(reportingOn dispatchQueue: DispatchQueue) -> DoseProgressReporter? {
        guard let bolus = state.unfinalizedBolus, !bolus.isFinished() else { return nil }
        return OpenPatchDoseProgressReporter(dose: bolus, reportingQueue: dispatchQueue)
    }

    public func enactBolus(units: Double, activationType: BolusActivationType, completion: @escaping (PumpManagerError?) -> Void) {
        let snapshot = state
        guard snapshot.phase == .active else {
            return completion(Self.map(.notReady(snapshot.phase)))
        }
        if let block = deliveryBlock(snapshot) { return completion(Self.map(block)) }
        guard snapshot.unfinalizedBolus.map({ $0.isFinished() }) ?? true else { return completion(Self.map(.bolusInProgress)) }
        let rounded = roundToSupportedBolusVolume(units: units)
        do { try snapshot.safetyLimits.validateBolus(units: rounded) } catch {
            return completion(Self.map(.limit(error as? LimitError ?? .notPositive)))
        }
        let pulses = UnitConversion.pulses(forUnits: rounded)
        let id = snapshot.nextBolusID
        mutateState { $0.nextBolusID = $0.nextBolusID &+ 1 == 0 ? 1 : $0.nextBolusID &+ 1 }
        setTransient(bolus: .some(.initiating))

        send(.bolus(id: id, pulses: UInt16(pulses))) { [weak self] result in
            guard let self else { return }
            self.setTransient(bolus: .some(nil))
            switch result {
            case .failure(let failure):
                completion(Self.map(failure))
            case .success:
                let dose = OpenPatchDose(kind: .bolus, id: id, units: rounded, startDate: Date(),
                                         duration: self.estimatedDuration(toBolus: rounded),
                                         automatic: activationType.isAutomatic, insulinType: self.state.insulinType)
                self.mutateState { $0.unfinalizedBolus = dose }
                self.reportDoses()
                self.scheduleFinalization()
                completion(nil)
            }
        }
    }

    public func cancelBolus(completion: @escaping (PumpManagerResult<DoseEntry?>) -> Void) {
        guard let bolus = state.unfinalizedBolus, !bolus.isFinished() else {
            return completion(.failure(Self.map(.noBolusToCancel)))
        }
        setTransient(bolus: .some(.canceling))
        send(.cancelBolus) { [weak self] result in
            guard let self else { return }
            self.setTransient(bolus: .some(nil))
            switch result {
            case .failure(let failure):
                completion(.failure(Self.map(failure)))
            case .success:
                // handle(event:) may already have finalized it with the pod-reported amount.
                if let current = self.state.unfinalizedBolus, current.id == bolus.id {
                    self.finalize(bolus: current.cancelled(at: Date()))
                }
                self.lock.lock()
                let finished = self.lastFinalizedBolus?.id == bolus.id ? self.lastFinalizedBolus : nil
                self.lock.unlock()
                completion(.success(finished?.doseEntry(isMutable: false)))
            }
        }
    }

    // MARK: Temp basal

    public func enactTempBasal(unitsPerHour: Double, for duration: TimeInterval, completion: @escaping (PumpManagerError?) -> Void) {
        let snapshot = state
        guard snapshot.phase == .active else { return completion(Self.map(.notReady(snapshot.phase))) }
        if duration >= 1, let block = deliveryBlock(snapshot) { return completion(Self.map(block)) }

        if duration < 1 {
            setTransient(basal: .some(.cancelingTempBasal))
            return send(.cancelTempBasal) { [weak self] result in
                guard let self else { return }
                self.setTransient(basal: .some(nil))
                switch result {
                case .failure(let failure): completion(Self.map(failure))
                case .success:
                    self.finalizeRunningTempBasal(cancelAt: Date())
                    self.reportDoses()
                    completion(nil)
                }
            }
        }

        let rate = UnitConversion.roundDownToPulse(unitsPerHour)
        do { try snapshot.safetyLimits.validateTempBasal(unitsPerHour: rate, duration: duration) } catch {
            return completion(Self.map(.limit(error as? LimitError ?? .notPositive)))
        }
        let minutes = UInt16(min(max((duration / 60).rounded(.up), 1), 720))
        setTransient(basal: .some(.initiatingTempBasal))
        send(.setTempBasal(rateTicks: UInt16(UnitConversion.pulses(forUnits: rate)), durationMinutes: minutes)) { [weak self] result in
            guard let self else { return }
            self.setTransient(basal: .some(nil))
            switch result {
            case .failure(let failure): completion(Self.map(failure))
            case .success:
                let now = Date()
                self.finalizeRunningTempBasal(cancelAt: now)
                let dose = OpenPatchDose(kind: .tempBasal, id: 0, units: rate, startDate: now, duration: TimeInterval(minutes) * 60,
                                         automatic: true, insulinType: self.state.insulinType)
                self.mutateState { $0.unfinalizedTempBasal = dose }
                self.reportDoses()
                self.scheduleFinalization()
                completion(nil)
            }
        }
    }

    // MARK: Suspend / resume

    public func suspendDelivery(completion: @escaping (Error?) -> Void) {
        let snapshot = state
        guard snapshot.phase == .active else { return completion(Self.map(.notReady(snapshot.phase))) }
        setTransient(basal: .some(.suspending))
        send(.suspend) { [weak self] result in
            guard let self else { return }
            self.setTransient(basal: .some(nil))
            switch result {
            case .failure(let failure): completion(Self.map(failure))
            case .success:
                let now = Date()
                // The pod aborts a running bolus and temp basal on suspend.
                if let bolus = self.state.unfinalizedBolus { self.finalize(bolus: bolus.cancelled(at: now)) }
                self.finalizeRunningTempBasal(cancelAt: now)
                self.mutateState { $0.suspendedAt = now; $0.phase = .suspended }
                self.reportDoses(extra: [.openPatchSuspend(at: now)])
                completion(nil)
            }
        }
    }

    public func resumeDelivery(completion: @escaping (Error?) -> Void) {
        let snapshot = state
        guard snapshot.phase == .suspended else { return completion(Self.map(.notReady(snapshot.phase))) }
        if let block = deliveryBlock(snapshot) { return completion(Self.map(block)) }
        setTransient(basal: .some(.resuming))
        send(.resume) { [weak self] result in
            guard let self else { return }
            self.setTransient(basal: .some(nil))
            switch result {
            case .failure(let failure): completion(Self.map(failure))
            case .success:
                let now = Date()
                self.mutateState { $0.suspendedAt = nil; $0.resumedAt = now; $0.phase = .active }
                self.reportDoses(extra: [.openPatchResume(at: now, insulinType: self.state.insulinType)])
                completion(nil)
            }
        }
    }

    // MARK: Settings sync

    public func syncBasalRateSchedule(items scheduleItems: [RepeatingScheduleValue<Double>],
                                      completion: @escaping (Result<BasalRateSchedule, Error>) -> Void) {
        guard scheduleItems.count <= PumpConstants.maxBasalSegments else { return completion(.failure(Self.map(.notConfigured))) }
        let segments = scheduleItems.map { BasalSegment(startOffset: $0.startTime, unitsPerHour: $0.value) }
        let program: BasalProgram
        do { program = try BasalProgram(segments: segments, limits: state.safetyLimits) } catch {
            return completion(.failure(Self.map(.notConfigured)))
        }
        guard let schedule = BasalRateSchedule(dailyItems: scheduleItems, timeZone: state.timeZone) else {
            return completion(.failure(Self.map(.notConfigured)))
        }
        mutateState { $0.basalSegments = segments }
        // Before pairing there is no pod to program yet; the schedule is sent at activation.
        guard state.phase != .unpaired, state.phase != .deactivated, state.isSetupCompleted else { return completion(.success(schedule)) }
        send(.setBasalProgram(program)) { result in
            switch result {
            case .success: completion(.success(schedule))
            case .failure(let failure): completion(.failure(Self.map(failure)))
            }
        }
    }

    public func syncDeliveryLimits(limits deliveryLimits: DeliveryLimits, completion: @escaping (Result<DeliveryLimits, Error>) -> Void) {
        let unitsPerHour = HKUnit.internationalUnit().unitDivided(by: .hour())
        let bolus = deliveryLimits.maximumBolus?.doubleValue(for: .internationalUnit())
        let basal = deliveryLimits.maximumBasalRate?.doubleValue(for: unitsPerHour)
        let limits = SafetyLimits(maxBolus: bolus ?? state.maxBolus, maxBasalRate: basal ?? state.maxBasalRate)
        mutateState { $0.maxBolus = limits.maxBolus; $0.maxBasalRate = limits.maxBasalRate }
        let applied = DeliveryLimits(maximumBasalRate: HKQuantity(unit: unitsPerHour, doubleValue: limits.maxBasalRate),
                                     maximumBolus: HKQuantity(unit: .internationalUnit(), doubleValue: limits.maxBolus))
        guard state.phase != .unpaired, state.phase != .deactivated else { return completion(.success(applied)) }
        send(.setLimits(limits)) { result in
            switch result {
            case .success: completion(.success(applied))
            case .failure(let failure): completion(.failure(Self.map(failure)))
            }
        }
    }

    // MARK: Deactivation

    public func prepareForDeactivation(_ completion: @escaping (Error?) -> Void) {
        let finish = { [weak self] in
            guard let self else { return completion(nil) }
            self.notifyDelegateOfDeactivation { completion(nil) }
        }
        guard state.phase == .active || state.phase == .suspended else { return finish() }
        send(.deactivate) { [weak self] _ in
            self?.transport.disconnect()
            finish()
        }
    }

    // MARK: Alerts / debug

    public func acknowledgeAlert(alertIdentifier: Alert.AlertIdentifier, completion: @escaping (Error?) -> Void) {
        guard alertIdentifier == OpenPatchAlert.podFault.rawValue else { return completion(nil) }
        send(.silenceAlarm) { result in
            if case .failure(let failure) = result { completion(Self.map(failure)) } else { completion(nil) }
        }
    }

    public func getSoundBaseURL() -> URL? { nil }
    public func getSounds() -> [Alert.Sound] { [] }

    public var debugDescription: String {
        """
        ## OpenPatchPumpManager
        status: \(status)
        \(state.debugDescription)
        transport connected: \(transport.isConnected)
        """
    }

    func log(_ message: String) {
        delegate.notify { delegate in
            delegate?.deviceManager(self, logEventForDeviceIdentifier: self.state.peripheralIdentifier?.uuidString, type: .connection, message: message, completion: nil)
        }
    }
}
