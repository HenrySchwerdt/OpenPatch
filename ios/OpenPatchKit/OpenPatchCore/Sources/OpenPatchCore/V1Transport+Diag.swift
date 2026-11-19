import Foundation

// Diagnostics on the wire (docs/06-diagnostics.md 5.4, 5.5). The decoders are tolerant: a diagnostic TLV with an unexpected size is
// skipped (never a crash, never a failed status), so a pod with a newer schema still talks to this app.

extension V1.Message {
    private func u64(_ tag: V1.Tag) -> UInt64? {
        guard let v = value(tag), v.count == 8 else { return nil }
        return v.enumerated().reduce(UInt64(0)) { $0 | UInt64($1.element) << (8 * UInt64($1.offset)) }
    }

    /// `DIAG_SUMMARY` (14 bytes). `nil` for a v1 pod and for a size this app does not understand.
    public var diagSummary: DiagSummary? { value(.diagSummary).flatMap { DiagSummary(bytes: $0) } }
    public var fruHealth: FruHealth? { u64(.fruHealth).map(FruHealth.init(raw:)) }
    public var podUID: PodUID? { u64(.podUID).map(PodUID.init(raw:)) }
    /// Every well-sized `DIAG_RECORD` (32 bytes) in order.
    public var diagRecords: [DiagRecord] {
        tlvs.filter { $0.tag == V1.Tag.diagRecord.rawValue }.compactMap { DiagRecord(bytes: $0.value) }
    }
    /// Latched set (`DIAG_LATCHED`: 4 to 64 bytes, a multiple of 4).
    public var latchedCodes: [DiagCode] {
        guard let v = value(.diagLatched), v.count >= 4, v.count <= 64, v.count % 4 == 0 else { return [] }
        return stride(from: 0, to: v.count, by: 4).map { i in
            DiagCode(raw: UInt32(v[i]) | UInt32(v[i + 1]) << 8 | UInt32(v[i + 2]) << 16 | UInt32(v[i + 3]) << 24)
        }
    }
    public var selfTestState: SelfTestState? {
        guard let v = value(.selftestState), v.count == 6 else { return nil }
        return SelfTestState(phaseRaw: v[0], kindRaw: v[1], stepsPassed: UInt16(v[2]) | UInt16(v[3]) << 8, stepsFailed: UInt16(v[4]) | UInt16(v[5]) << 8)
    }
    public var diagCode: DiagCode? { u32(.diagCode).map(DiagCode.init(raw:)) }
}

extension V1Transport {
    // MARK: Commands

    public func getFaultLog(from: UInt32, completion: @escaping (Result<FaultLog, DiagCommandError>) -> Void) {
        guard link.isConnected else { return completion(.failure(.transport(.notConnected))) }
        ensureSession { [weak self] result in
            guard let self else { return }
            if case .failure(let error) = result { return completion(.failure(.transport(error))) }
            self.fetchFaultLog(from: from, into: FaultLog(), pagesLeft: 64, completion: completion)
        }
    }

    /// Pages `GetFaultLog` (4 records per frame) until the pod's `NEXT_DIAG_ID`. Records below the cursor are dropped (dedupe by id).
    func fetchFaultLog(from cursor: UInt32, into log: FaultLog, pagesLeft: Int, completion: @escaping (Result<FaultLog, DiagCommandError>) -> Void) {
        perform(.getFaultLog, [V1.TLV(.fromID, u32: cursor), V1.TLV(.maxEvents, u8: 4)]) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error): completion(.failure(.transport(error)))
            case .success(let message):
                guard message.result == .ok else { return completion(.failure(Self.diagFailure(message))) }
                var log = log
                log.nextID = message.u32(.nextDiagID) ?? log.nextID
                log.oldestID = message.u32(.oldestDiagID) ?? log.oldestID
                let latched = message.latchedCodes
                if !latched.isEmpty { log.latched = latched }
                let fresh = message.diagRecords.filter { cursor == 0 || $0.recID >= cursor }
                log.records += fresh
                guard let last = fresh.last, last.recID &+ 1 < log.nextID, pagesLeft > 1 else { return completion(.success(log)) }
                self.fetchFaultLog(from: last.recID &+ 1, into: log, pagesLeft: pagesLeft - 1, completion: completion)
            }
        }
    }

    public func runSelfTest(_ kind: SelfTestState.Kind, completion: @escaping (Result<SelfTestState, DiagCommandError>) -> Void) {
        diagnosticRequest(.runSelfTest, [V1.TLV(.subOp, u8: kind.rawValue)], completion: completion) { message in
            message.selfTestState ?? SelfTestState(phaseRaw: SelfTestState.Phase.done.rawValue, kindRaw: kind.rawValue)
        }
    }

    public func clearDiag(_ code: DiagCode?, completion: @escaping (Result<DiagSummary, DiagCommandError>) -> Void) {
        diagnosticRequest(.clearDiag, [V1.TLV(.diagCode, u32: code?.raw ?? 0)], completion: completion) { message in
            message.diagSummary ?? DiagSummary()
        }
    }

    private func diagnosticRequest<T>(_ id: V1.CommandID, _ tlvs: [V1.TLV], completion: @escaping (Result<T, DiagCommandError>) -> Void,
                                      parse: @escaping (V1.Message) -> T) {
        guard link.isConnected else { return completion(.failure(.transport(.notConnected))) }
        ensureSession { [weak self] result in
            guard let self else { return }
            if case .failure(let error) = result { return completion(.failure(.transport(error))) }
            self.perform(id, tlvs) { result in
                switch result {
                case .failure(let error): completion(.failure(.transport(error)))
                case .success(let message):
                    guard message.result == .ok else { return completion(.failure(Self.diagFailure(message))) }
                    completion(.success(parse(message)))
                }
            }
        }
    }

    /// A refusal as a `DiagCommandError`, with the `DIAG_CODE` the pod named (the root latched code of a `Latched` refusal).
    static func diagFailure(_ message: V1.Message) -> DiagCommandError {
        let code = message.result ?? .frame
        let reason = nack(for: code, command: .getStatus) ?? .invalidState
        return .nack(reason, code: message.diagCode)
    }

    // MARK: Notifications (Alert characteristic, frame type 0x90, nonce direction 2)

    /// Decodes one notification frame from the Alert characteristic and forwards it as a `PodEvent`: kind 2 fault (legacy bits),
    /// 5 `DIAG_RAISED` (with the complete record), 6 `DIAG_CLEARED`, 7 `SELFTEST_PROGRESS`. Anything undecodable is dropped: notifications
    /// are lossy by design, the reliable path is the pull in `refreshStatus`.
    public func handleNotification(_ frame: Data) {
        lock.lock(); let secure = channel; lock.unlock()
        let decoded: V1.Message? = secure != nil ? try? secure?.open(frame, as: .notification) : try? V1.decode(frame)
        guard let message = decoded, message.type == SecureChannel.notificationType,
              let kind = message.u8(.notifyKind), let arg = message.u32(.notifyArg) else { return }
        switch kind {
        case 2: Self.faultCode(mask: UInt16(truncatingIfNeeded: arg)).map { eventHandler?(.fault($0)) }
        case 5: message.diagRecords.first.map { eventHandler?(.diag($0)) }
        case 6: eventHandler?(.diagCleared(DiagCode(raw: arg)))
        case 7: eventHandler?(.selfTest(passed: UInt16(truncatingIfNeeded: arg >> 16), failed: UInt16(truncatingIfNeeded: arg)))
        default: break
        }
    }

    // MARK: Pull path

    /// Restores the id of the next record to fetch (persisted by the owner per pod UID).
    public func restoreDiagCursor(_ next: UInt32?) { lock.lock(); diagCursor = next; diagNextLow = nil; lock.unlock() }
    public var currentDiagCursor: UInt32? { lock.lock(); defer { lock.unlock() }; return diagCursor }

    /// When the pod's `next_rec_id_lo` moved since the last status, fetches the new records and forwards them as events (W, F, L
    /// records as `.diag`, clear records as `.diagCleared`; information records are log only). The first sync after (re)connect
    /// forwards only records that are still active, so existing faults raise their alert once.
    func pollDiag(_ summary: DiagSummary?, then done: @escaping () -> Void) {
        guard let summary else { return done() }
        lock.lock(); let cursor = diagCursor; let lastLow = diagNextLow; lock.unlock()
        if cursor != nil, lastLow == summary.nextRecIDLow { return done() }
        fetchFaultLog(from: cursor ?? 0, into: FaultLog(), pagesLeft: 16) { [weak self] result in
            guard let self else { return }
            guard case .success(let log) = result else { return done() }
            let firstSync = cursor == nil
            for record in log.records {
                if record.isClearRecord {
                    if !firstSync { self.eventHandler?(.diagCleared(record.code)) }
                } else if record.severity >= .warning, !firstSync || record.isActive {
                    self.eventHandler?(.diag(record))
                }
            }
            self.lock.lock(); self.diagCursor = log.nextID; self.diagNextLow = summary.nextRecIDLow; self.lock.unlock()
            done()
        }
    }
}
