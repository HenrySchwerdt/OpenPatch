import Foundation

/// One request/response exchange of raw frames over the radio (CoreBluetooth in the app).
public protocol FrameLink: AnyObject {
    var isConnected: Bool { get }
    func connect(completion: @escaping (Result<Void, TransportError>) -> Void)
    func disconnect()
    /// Sends exactly one frame and completes with the response frame carrying the same `seq`.
    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void)
}

/// Adapts the app's domain commands to OpenPatch protocol v1 (firmware/docs/openpatch-protocol.md).
///
/// The pod's wire protocol is deliberately smaller than the domain model, so this class bridges the gaps:
///
/// | domain                      | wire v1                                                                  |
/// |-----------------------------|--------------------------------------------------------------------------|
/// | hello / setTime / getStatus | GetStatus (+ TIME_OF_DAY_MS)                                             |
/// | setLimits                   | local only (pod limits are firmware config; the app enforces its own)    |
/// | confirmFill                 | Fill/Prime sub-op 1                                                      |
/// | prime                       | Fill/Prime sub-op 2 (steps for `PumpConstants.primeUnits`)               |
/// | confirmAttached             | Resume (the pod boots suspended)                                         |
/// | deactivate                  | Suspend (pod-side nothing to deactivate; lifecycle is app state)          |
/// | silenceAlarm                | Acknowledge                                                              |
/// | pushed `PodEvent`s          | GetHistory polling after every status read                                |
///
/// The pod reports no lifecycle phase and no bolus id: both are tracked here (`phaseHint`, `lastBolus`).
public final class V1Transport: OpenPatchTransport {
    let link: FrameLink
    private let clock: () -> Date
    private let timeOfDayMilliseconds: () -> UInt32
    let lock = NSLock()

    private var sequence: UInt16
    private var phaseHint: PodPhase
    private var lastBolus: (id: UInt16, pulses: UInt16)?
    private var historyCursor: UInt32?
    private var wasFaulted = false
    /// Id of the next diagnostic record to fetch (`nil` = never synced) and the pod's `next_rec_id_lo` at that time.
    var diagCursor: UInt32?
    var diagNextLow: UInt16?
    /// Drive calibration from the last status. `prime` is refused without a known one (no assumed volume per step).
    private var calibration: DriveCalibration?
    private var lastReleaseDeliveredMU: UInt32?
    /// Application layer security (docs/04-protocol.md). With a pairing secret every connection first runs the session
    /// handshake and all commands / responses are AES-CCM protected; without one the transport speaks plaintext
    /// (simulator, `dev-plaintext` pods only).
    private var pairingSecret: [UInt8]?
    var channel: SecureChannel?
    private var sessionWaiters: [(Result<Void, TransportError>) -> Void] = []
    private let random: (Int) -> [UInt8]

    public var eventHandler: ((PodEvent) -> Void)?
    public var isConnected: Bool { link.isConnected }
    /// A session key agreement completed on the current connection.
    public var hasSession: Bool { lock.lock(); defer { lock.unlock() }; return channel != nil }
    /// Replaces the pairing secret (for example after `pair`, or once it was read back from the Keychain).
    public func setPairingSecret(_ secret: [UInt8]?) { lock.lock(); pairingSecret = secret; channel = nil; lock.unlock() }

    public static func systemRandom(_ count: Int) -> [UInt8] {
        var generator = SystemRandomNumberGenerator()
        return (0..<count).map { _ in UInt8.random(in: 0...255, using: &generator) }
    }

    /// State that must survive an app restart. Reported whenever it changes, before the exchange it belongs to
    /// (sequence) or before events are delivered (cursor). The owner persists it and passes it back into `init`.
    public struct Checkpoint: Equatable {
        /// Next command `seq` to use. Persisted *before* the frame is sent so a crash cannot reuse a `seq`.
        public var nextSequence: UInt16
        /// ID of the next history event to fetch; everything below it has been delivered.
        public var historyCursor: UInt32?
    }
    public var checkpointHandler: ((Checkpoint) -> Void)?

    /// - Parameters:
    ///   - initialSequence: first command `seq`. Must exceed the highest `seq` the pod accepted before
    ///     (replay protection survives reboots only if the platform stores it, spec 5.2).
    ///   - pairingSecret: the 32 byte secret created by `pair` (keep it in the Keychain). When set, a session handshake runs
    ///     before the first command of every connection and the sequence counter restarts at 1 with each session.
    ///   - random: source of the handshake's ephemeral keys and nonces; must be cryptographically secure.
    public init(link: FrameLink, initialPhase: PodPhase, initialSequence: UInt16 = 1, initialHistoryCursor: UInt32? = nil,
                pairingSecret: [UInt8]? = nil, random: @escaping (Int) -> [UInt8] = V1Transport.systemRandom,
                clock: @escaping () -> Date = Date.init,
                timeOfDayMilliseconds: @escaping () -> UInt32 = V1Transport.localTimeOfDay) {
        self.pairingSecret = pairingSecret
        self.random = random
        self.link = link
        self.phaseHint = initialPhase
        self.sequence = initialSequence
        self.historyCursor = initialHistoryCursor
        self.clock = clock
        self.timeOfDayMilliseconds = timeOfDayMilliseconds
    }

    public static func localTimeOfDay() -> UInt32 {
        let now = Date()
        let seconds = now.timeIntervalSince(Calendar.current.startOfDay(for: now))
        return UInt32(max(seconds, 0) * 1000)
    }

    public func connect(completion: @escaping (Result<Void, TransportError>) -> Void) {
        lock.lock(); channel = nil; lock.unlock()    // session keys never outlive a connection
        link.connect(completion: completion)
    }
    public func disconnect() {
        lock.lock(); channel = nil; lock.unlock()
        link.disconnect()
    }

    // MARK: Key agreement (docs/04-protocol.md)

    private static func transportError(_ failure: SessionHandshake.Failure) -> TransportError {
        switch failure {
        case .malformed: return .malformedResponse
        case .rejected(let code): return code == V1.Result.pair.rawValue ? .notPaired : .sessionFailed
        case .badConfirmation, .lowOrderPoint: return .sessionFailed
        }
    }

    private func runHandshake(_ initiator: SessionHandshake.Initiator, completion: @escaping (Result<SessionHandshake.Outcome, TransportError>) -> Void) {
        let initFrame = initiator.initFrame()
        link.exchange(frame: initFrame, seq: 0) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error): completion(.failure(error))
            case .success(let response):
                do {
                    let finish = try initiator.finishFrame(initResponse: response)
                    self.link.exchange(frame: finish, seq: 1) { result in
                        switch result {
                        case .failure(let error): completion(.failure(error))
                        case .success(let reply):
                            do { completion(.success(try initiator.complete(finishResponse: reply))) }
                            catch { completion(.failure(Self.transportError(error as? SessionHandshake.Failure ?? .malformed))) }
                        }
                    }
                } catch {
                    completion(.failure(Self.transportError(error as? SessionHandshake.Failure ?? .malformed)))
                }
            }
        }
    }

    /// Creates the long-term pairing secret. Only works while the pod's button window is open (press the button first;
    /// call after the BLE bond is made). The caller must persist the returned secret (Keychain, this device only). The
    /// transport keeps it in memory and uses it for the following sessions. `oob` is an optional out-of-band code.
    public func pair(oob: [UInt8] = [], completion: @escaping (Result<[UInt8], TransportError>) -> Void) {
        guard link.isConnected else { return completion(.failure(.notConnected)) }
        guard let initiator = try? SessionHandshake.Initiator(pairingWithOOB: oob, random: random) else { return completion(.failure(.sessionFailed)) }
        runHandshake(initiator) { [weak self] result in
            switch result {
            case .failure(let error): completion(.failure(error))
            case .success(.paired(let secret)):
                self?.setPairingSecret(secret)
                completion(.success(secret))
            case .success: completion(.failure(.malformedResponse))
            }
        }
    }

    /// Runs the session handshake with the stored pairing secret and installs the session (sequence restarts at 1).
    public func establishSession(completion: @escaping (Result<Void, TransportError>) -> Void) {
        guard link.isConnected else { return completion(.failure(.notConnected)) }
        lock.lock(); let secret = pairingSecret; lock.unlock()
        guard let secret else { return completion(.failure(.notPaired)) }
        guard let initiator = try? SessionHandshake.Initiator(sessionWith: secret, random: random) else { return completion(.failure(.sessionFailed)) }
        runHandshake(initiator) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error): completion(.failure(error))
            case .success(.session(let keys)):
                self.lock.lock()
                self.channel = SecureChannel(keys: keys)
                self.sequence = 1                      // the sequence space is per session
                let checkpoint = Checkpoint(nextSequence: 1, historyCursor: self.historyCursor)
                self.lock.unlock()
                self.checkpointHandler?(checkpoint)
                completion(.success(()))
            case .success: completion(.failure(.malformedResponse))
            }
        }
    }

    /// With a pairing secret every command needs a session: run the handshake once, however many sends wait for it.
    func ensureSession(_ done: @escaping (Result<Void, TransportError>) -> Void) {
        lock.lock()
        if pairingSecret == nil || channel != nil { lock.unlock(); return done(.success(())) }
        sessionWaiters.append(done)
        let leader = sessionWaiters.count == 1
        lock.unlock()
        guard leader else { return }
        establishSession { [weak self] result in
            guard let self else { return }
            self.lock.lock(); let waiters = self.sessionWaiters; self.sessionWaiters = []; self.lock.unlock()
            waiters.forEach { $0(result) }
        }
    }

    // MARK: Domain -> wire

    private enum Plan {
        case status
        case local
        case reject(NackReason)
        case request(V1.CommandID, [V1.TLV], sideEffect: () -> Void)
    }

    private func plan(for command: Command) -> Plan {
        switch command {
        case .hello:
            lock.lock(); defer { lock.unlock() }
            if phaseHint == .unpaired || phaseHint == .deactivated { phaseHint = .paired }
            return .status
        case .getStatus, .setTime:
            return .status
        case .setLimits:
            return .local
        case .setBasalProgram(let program):
            let segments = program.segments
            guard segments.count <= PumpConstants.maxBasalSegments else { return .reject(.limitExceeded) }   // wire allows 1-24 segments
            let tlvs = segments.map { segment -> V1.TLV in
                var w = ByteWriter()
                w.u8(UInt8(segment.startOffset / PumpConstants.basalSlotDuration))
                w.u16(UInt16(clamping: UnitConversion.pulses(forUnits: segment.unitsPerHour) * 50))
                return V1.TLV(tag: V1.Tag.basalSeg.rawValue, value: w.bytes)
            }
            return .request(.setBasalSchedule, tlvs, sideEffect: {})
        case .setTempBasal(let ticks, let minutes):
            let rounded = min(max(((Int(minutes) + 29) / 30) * 30, 30), 720)   // wire: multiples of 30 min
            return .request(.setTempBasal, [V1.TLV(.rateMUh, u16: ticks * 50), V1.TLV(.durationMin, u16: UInt16(rounded))], sideEffect: {})
        case .cancelTempBasal:
            return .request(.cancelTempBasal, [], sideEffect: {})
        case .bolus(let id, let pulses):
            return .request(.bolus, [V1.TLV(.amountMU, u32: UInt32(pulses) * 50)], sideEffect: { [unowned self] in
                lock.lock(); lastBolus = (id, pulses); lock.unlock()
            })
        case .cancelBolus:
            return .request(.cancelBolus, [], sideEffect: {})
        case .suspend:
            return .request(.suspend, [], sideEffect: { [unowned self] in setPhase(.suspended, from: [.active]) })
        case .resume:
            return .request(.resume, [], sideEffect: { [unowned self] in setPhase(.active, from: [.suspended, .primed]) })
        case .confirmAttached:
            return .request(.resume, [], sideEffect: { [unowned self] in setPhase(.active, from: [.primed, .suspended]) })
        case .deactivate:
            return .request(.suspend, [], sideEffect: { [unowned self] in setPhase(.deactivated, from: PodPhase.allCases) })
        case .confirmFill(let pulses):
            return .request(.fillPrime, [V1.TLV(.subOp, u8: 1), V1.TLV(.fillMU, u32: UInt32(pulses) * 50)], sideEffect: { [unowned self] in setPhase(.filled, from: [.paired, .deactivated]) })
        case .prime:
            lock.lock(); let cal = calibration; lock.unlock()
            // The volume per step comes from the pod's own calibration; without a known one nothing is primed.
            guard let cal, cal.isKnown else { return .reject(.calibration) }
            let steps = UInt16(min(UnitConversion.steps(forUnits: PumpConstants.primeUnits, calibration: cal), cal.maxPrimeSteps))
            return .request(.fillPrime, [V1.TLV(.subOp, u8: 2), V1.TLV(.primeSteps, u16: steps)], sideEffect: { [unowned self] in
                setPhase(.primed, from: [.filled])
                eventHandler?(.primeCompleted)    // wire prime is synchronous: done when the response arrives
            })
        case .silenceAlarm:
            return .request(.acknowledge, [], sideEffect: {})
        case .setPairing(let pairID, let role):
            return .request(.setPairing, [V1.TLV(.pairID, u32: pairID), V1.TLV(.role, u8: role.rawValue)], sideEffect: {})
        case .activatePod(let pairID, let activationID, let program, let temp):
            guard program.segments.count <= PumpConstants.maxBasalSegments else { return .reject(.limitExceeded) }
            var tlvs = [V1.TLV(.pairID, u32: pairID), V1.TLV(.activationID, u32: activationID)]
            tlvs += program.segments.map { segment -> V1.TLV in
                var w = ByteWriter()
                w.u8(UInt8(segment.startOffset / PumpConstants.basalSlotDuration))
                w.u16(UInt16(clamping: UnitConversion.pulses(forUnits: segment.unitsPerHour) * 50))
                return V1.TLV(tag: V1.Tag.basalSeg.rawValue, value: w.bytes)
            }
            if let temp, temp.remainingMinutes > 0 {
                let rounded = min(max(((Int(temp.remainingMinutes) + 29) / 30) * 30, 30), 720)
                tlvs += [V1.TLV(.rateMUh, u16: temp.rateTicks * 50), V1.TLV(.durationMin, u16: UInt16(rounded))]
            }
            return .request(.activate, tlvs, sideEffect: {})
        case .releasePod(let pairID):
            return .request(.release, [V1.TLV(.pairID, u32: pairID)], sideEffect: { [unowned self] in
                setPhase(.deactivated, from: [.filled, .priming, .primed, .active, .suspended, .faulted])
            })
        }
    }

    /// Report for the status that answers a `releasePod` (consumed once).
    private func releaseReport(_ m: V1.Message) -> ReleaseReport? {
        lock.lock(); defer { lock.unlock() }
        guard let delivered = lastReleaseDeliveredMU else { return nil }
        lastReleaseDeliveredMU = nil
        return ReleaseReport(deliveredSinceActivationUnits: Double(delivered) / 1000,
                             finalReservoirUnits: Double(m.u32(.reservoirMU) ?? 0) / 1000)
    }

    private func setPhase(_ new: PodPhase, from allowed: [PodPhase]) {
        lock.lock(); defer { lock.unlock() }
        if allowed.contains(phaseHint) { phaseHint = new }
    }

    public func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {
        guard link.isConnected else { return completion(.failure(.notConnected)) }
        ensureSession { [weak self] result in
            guard let self else { return }
            if case .failure(let error) = result { return completion(.failure(error)) }
            self.sendPlanned(command, completion: completion)
        }
    }

    private func sendPlanned(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {
        switch plan(for: command) {
        case .local:
            refreshStatus(completion: completion)
        case .status:
            refreshStatus(completion: completion)
        case .reject(let reason):
            completion(.success(.rejected(reason)))
        case .request(let id, let tlvs, let sideEffect):
            perform(id, tlvs) { [weak self] result in
                guard let self else { return }
                switch result {
                case .failure(let error): completion(.failure(error))
                case .success(let message):
                    let code = message.result ?? .frame
                    if let reason = Self.nack(for: code, command: command) { return completion(.success(.rejected(reason))) }
                    sideEffect()
                    if command.kind == .releasePod { self.captureRelease(message) }
                    self.refreshStatus(completion: completion)
                }
            }
        }
    }

    // MARK: Exchange

    func perform(_ id: V1.CommandID, _ tlvs: [V1.TLV], completion: @escaping (Result<V1.Message, TransportError>) -> Void) {
        lock.lock()
        let seq = sequence
        sequence = sequence >= 0xFFFE ? 0xFFFE : sequence + 1   // 0xFFFF reserved; at the end a new session is needed
        let checkpoint = Checkpoint(nextSequence: sequence, historyCursor: historyCursor)
        let secure = channel
        lock.unlock()
        checkpointHandler?(checkpoint)
        let withTime = tlvs + [V1.TLV(.timeOfDayMS, u32: timeOfDayMilliseconds())]
        let request = V1.Message(type: id.rawValue, seq: seq, tlvs: withTime)
        let frame = secure?.seal(request) ?? V1.encode(request)
        link.exchange(frame: frame, seq: seq) { result in
            switch result {
            case .failure(let error): completion(.failure(error))
            case .success(let data):
                // With a session only authenticated, decrypted responses count: a plaintext reply is refused.
                let decoded: V1.Message? = secure != nil ? try? secure?.open(data, as: .response) : try? V1.decode(data)
                guard let message = decoded, message.isResponse, message.seq == seq,
                      message.type == (id.rawValue | V1.responseFlag) else { return completion(.failure(.malformedResponse)) }
                completion(.success(message))
            }
        }
    }

    static func nack(for code: V1.Result, command: Command) -> NackReason? {
        switch code {
        case .ok: return nil
        case .notFound:
            // cancelling something that is not running is already the desired end state
            return command.kind == .cancelBolus || command.kind == .cancelTempBasal ? nil : .invalidState
        case .badArg, .frame, .tooLarge, .crc, .version: return .malformed
        case .limit: return .limitExceeded
        case .hourly: return .hourlyLimit
        case .busy: return .busy
        case .fault, .suspended, .notSuspended, .persists: return .invalidState
        case .reservoir: return .insufficientReservoir
        case .unsupported: return .unsupported
        case .replay, .auth, .session: return .session
        case .notDocked: return .notDocked
        case .released: return .released
        case .alreadyActive: return .alreadyActive
        case .pair: return .pairMismatch
        case .charging: return .charging
        case .wearExpired: return .invalidState
        case .selfTestRefused: return .selfTestRefused
        case .latched: return .latched
        case .notClearable: return .notClearable
        }
    }

    // MARK: Status + history

    private func refreshStatus(completion: @escaping (Result<Response, TransportError>) -> Void) {
        perform(.getStatus, []) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error): completion(.failure(error))
            case .success(let message):
                guard message.result == .ok else { return completion(.success(.rejected(.invalidState))) }
                let status = self.parseStatus(message)
                self.pollDiag(status.diag) {
                    self.pollHistory(upTo: message.u32(.nextEventID)) {
                        completion(.success(.ok(status)))
                    }
                }
            }
        }
    }

    private func captureRelease(_ message: V1.Message) {
        lock.lock(); lastReleaseDeliveredMU = message.u32(.actDeliveredMU); lock.unlock()
    }

    static func parseCalibration(_ m: V1.Message) -> DriveCalibration? {
        guard let v = m.value(.driveCal), v.count == 10 else { return nil }
        var r = ByteReader(v)
        guard let id = try? r.u16(), let uu = try? r.u32(), let spr = try? r.u16(), let ratio = try? r.u16(), uu != 0 else { return nil }
        return DriveCalibration(driveID: id, microUnitsPerStep: uu, stepsPerRevolution: spr, gearRatioTimes100: ratio)
    }

    static func parsePairing(_ m: V1.Message, flags: V1.StateFlags) -> PodPairingInfo? {
        guard let v = m.value(.podInfo), v.count == 10 else { return nil }
        var r = ByteReader(v)
        guard let pair = try? r.u32(), let role = try? r.u8(), let state = try? r.u8(), let wear = try? r.u32() else { return nil }
        return PodPairingInfo(pairID: pair, role: PodRole(rawValue: role), deliveryState: PodDeliveryState(rawValue: state) ?? .released,
                              isDocked: flags.contains(.docked), isActive: flags.contains(.activePod), wearSeconds: wear,
                              wearWarning: flags.contains(.wearWarning))
    }

    func parseStatus(_ m: V1.Message) -> PodStatus {
        let flags = V1.StateFlags(rawValue: m.u16(.stateFlags) ?? 0)
        let faultMask = m.u16(.faultMask) ?? 0
        let remainingPulses = Int((m.u32(.bolusRemainingMU) ?? 0) / 50)
        let cal = Self.parseCalibration(m)
        let pairing = Self.parsePairing(m, flags: flags)

        lock.lock()
        calibration = cal
        var phase = phaseHint
        if let pairing, !pairing.isActive, [.priming, .primed, .active, .suspended].contains(phase) {
            phase = .deactivated   // the pod says it is released (charger, wear, a Release we never saw answered)
        } else if faultMask != 0 {
            phase = .faulted
        } else if phase == .faulted {
            phase = .suspended          // Acknowledge never resumes delivery
        } else if phase == .active || phase == .suspended {
            phase = flags.contains(.suspended) ? .suspended : .active
        }
        phaseHint = phase
        wasFaulted = faultMask != 0
        let bolusInfo = lastBolus
        lock.unlock()

        var bolus: BolusStatus?
        if flags.contains(.bolusActive), remainingPulses > 0 {
            let requested = bolusInfo.map { Int($0.pulses) } ?? remainingPulses
            bolus = BolusStatus(id: bolusInfo?.id ?? 0, requestedPulses: UInt16(clamping: requested),
                                deliveredPulses: UInt16(clamping: max(requested - remainingPulses, 0)))
        }
        let tempRate = m.u16(.tempRateMUh) ?? 0
        let temp = flags.contains(.tempActive)
            ? TempBasalStatus(rateTicks: tempRate / 50, remainingMinutes: m.u16(.tempRemainingMin) ?? 0) : nil
        return PodStatus(phase: phase,
                         reservoirPulses: UInt16(clamping: Int((m.u32(.reservoirMU) ?? 0) / 50)),
                         batteryPercent: Self.batteryPercent(millivolts: m.u16(.batteryMV) ?? 0),
                         podTime: clock(),
                         totalDeliveredPulses: (m.u32(.deliveredMU) ?? 0) / 50,
                         bolus: bolus, tempBasal: temp, faultCode: Self.faultCode(mask: faultMask),
                         driveCalibration: cal, pairing: pairing, releaseReport: releaseReport(m),
                         diag: m.diagSummary, fruHealth: m.fruHealth, uid: m.podUID)
    }

    /// Crude linear Li-Po estimate: 3.3 V (critical) = 0 %, 4.2 V = 100 %. Replace with the measured discharge curve.
    static func batteryPercent(millivolts: UInt16) -> UInt8 {
        UInt8(min(max((Double(millivolts) - 3300) / 900 * 100, 0), 100).rounded())
    }

    static func faultCode(mask: UInt16) -> FaultCode? {
        guard mask != 0 else { return nil }
        if mask & V1.FaultBit.noCalibration != 0 { return .noCalibration }
        if mask & V1.FaultBit.wearExpired != 0 { return .wearExpired }
        if mask & V1.FaultBit.occlusion != 0 { return .occlusion }
        if mask & V1.FaultBit.reservoirEmpty != 0 { return .reservoirEmpty }
        if mask & V1.FaultBit.encoderDeviation != 0 { return .encoderMismatch }
        if mask & V1.FaultBit.batteryCritical != 0 { return .batteryCritical }
        if mask & V1.FaultBit.limitExceeded != 0 { return .limitVeto }
        return .internalError
    }

    /// Fetches events newer than the cursor and forwards them as domain events. The first poll after a
    /// (re)connect only sets the cursor so old history is not replayed as new alarms.
    private func pollHistory(upTo next: UInt32?, then done: @escaping () -> Void, pagesLeft: Int = 8) {
        guard let next else { return done() }
        lock.lock()
        guard let cursor = historyCursor else {
            historyCursor = next
            let checkpoint = Checkpoint(nextSequence: sequence, historyCursor: next)
            lock.unlock()
            checkpointHandler?(checkpoint)
            return done()
        }
        lock.unlock()
        guard next > cursor, pagesLeft > 0 else { return done() }

        perform(.getHistory, [V1.TLV(.fromID, u32: cursor), V1.TLV(.maxEvents, u8: 10)]) { [weak self] result in
            guard let self else { return }
            guard case .success(let message) = result, message.result == .ok else { return done() }
            // Dedupe by persistent event ID: never deliver anything below the cursor.
            let events = message.historyEvents.filter { $0.id >= cursor }
            guard let last = events.last else {
                self.setCursor(next)    // nothing newer retrievable
                return done()
            }
            // At-least-once: the cursor is reported with the events' delivery; the owner persists it right after.
            events.compactMap(self.domainEvent(for:)).forEach { self.eventHandler?($0) }
            self.setCursor(last.id + 1)
            self.pollHistory(upTo: next, then: done, pagesLeft: pagesLeft - 1)
        }
    }

    private func setCursor(_ value: UInt32) {
        lock.lock()
        historyCursor = value
        let checkpoint = Checkpoint(nextSequence: sequence, historyCursor: value)
        lock.unlock()
        checkpointHandler?(checkpoint)
    }

    func domainEvent(for event: V1.HistoryEvent) -> PodEvent? {
        guard let type = V1.HistoryType(rawValue: event.type) else { return nil }
        lock.lock(); let bolus = lastBolus; lock.unlock()
        switch type {
        case .bolusDone:
            return bolus.map { .bolusCompleted(id: $0.id, deliveredPulses: $0.pulses) }
        case .bolusCancel:
            return bolus.map { .bolusCompleted(id: $0.id, deliveredPulses: UInt16(clamping: max(Int($0.pulses) - Int(event.a) / 50, 0))) }
        case .tempDone, .tempCancel: return .tempBasalEnded
        case .tempCommFallback: return .tempBasalRevertedCommLoss
        case .fault: return Self.faultCode(mask: UInt16(truncatingIfNeeded: event.a)).map(PodEvent.fault)
        case .lowReservoir: return .lowReservoir(pulses: UInt16(clamping: Int(event.a) / 50))
        case .lowBattery: return .batteryLow(percent: Self.batteryPercent(millivolts: UInt16(clamping: Int(event.a))))
        case .undocked: return .docked(false)
        case .docked: return .docked(true)
        case .wearWarning: return .wearWarning
        case .wearExpired: return .wearExpired
        case .release:
            let reason: ReleaseReason = event.b == 1 ? .charger : (event.b == 2 ? .wear : .command)
            return .released(deliveredUnits: Double(max(event.a, 0)) / 1000, reason: reason)
        case .diag:
            return nil    // history event 31 only tells a v1 reader that something happened: records come from the pull path
        default: return nil
        }
    }
}
