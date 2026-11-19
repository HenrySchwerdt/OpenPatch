import Foundation

/// Diagnostic state of the simulated pod: the same rules as the firmware core (`openpatch-core/src/diag.rs`) in a simpler form, so every
/// catalogue code can be driven end to end in app tests without hardware (docs/06-diagnostics.md 5.5).
struct SimulatedDiagState {
    static let ringCapacity = 64
    var records: [DiagRecord] = []
    var nextID: UInt32 = 1
    /// Active (W/F/L) records by catalogue identity -> record id.
    var active: [DiagCode: UInt32] = [:]
    var latched: [DiagCode] = []
    /// Codes whose verification test "passed" (test hook).
    var verified: Set<DiagCode> = []
    var postState: UInt8 = 0
    var proven: Set<Fru> = []
    var uptimeSeconds: UInt32 = 0
}

extension SimulatedPod {
    /// Drives a catalogue code through the pod as if the firmware had raised it: a record (32 byte, with severity / FRU / action from
    /// the catalogue unless overridden), the active and latched sets, the `.diag` event, and for F and L the legacy fault
    /// (`faultCode`, `phase = .faulted`, `.fault` event) so legacy flows still see a stopped pod. An unknown code behaves like the
    /// firmware's `7-7C-003`: a fault with the record's own severity (default FAULT), FRU firmware and action "report".
    @discardableResult
    public func inject(_ code: DiagCode, ctx: (a: Int32, b: Int32, c: UInt32) = (0, 0, 0), cause: DiagRecord? = nil,
                       severity: DiagSeverity? = nil, fru: Fru? = nil, fru2: Fru? = nil, action: DiagAction? = nil) -> DiagRecord {
        let entry = DiagCatalogue.lookup(code)
        let sev = severity ?? entry?.severity ?? .fault
        let identity = code.identity
        var flags: DiagRecord.Flags = cause == nil ? [.root] : []
        if sev >= .warning { flags.insert(.active) }
        if sev == .latched { flags.insert(.latched) }
        if !diag.records.contains(where: { $0.code.identity == identity }) { flags.insert(.firstSinceBoot) }
        // same identity still active: coalesce (count, last context), unless escalating
        if let id = diag.active[identity], let index = diag.records.firstIndex(where: { $0.recID == id }), diag.records[index].severity >= sev, sev >= .warning {
            diag.records[index].count = diag.records[index].count == 255 ? 255 : diag.records[index].count + 1
            diag.records[index].ctxA = ctx.a; diag.records[index].ctxB = ctx.b; diag.records[index].ctxC = ctx.c
            return diag.records[index]
        }
        if diag.active[identity] != nil, sev >= .warning { flags.insert(.escalated) }
        let record = DiagRecord(recID: diag.nextID, code: code, severityRaw: sev.rawValue,
                                actionRaw: (action ?? entry?.action ?? .reportBug).rawValue,
                                fruRaw: (fru ?? entry?.fru ?? .fw).rawValue, fru2Raw: (fru2 ?? entry?.fru2)?.rawValue ?? 0,
                                podSeconds: diag.uptimeSeconds, ctxA: ctx.a, ctxB: ctx.b, ctxC: ctx.c, count: 1, flags: flags,
                                causeRec: cause.map { UInt16(truncatingIfNeeded: $0.recID) } ?? 0)
        diag.nextID &+= 1
        diag.records.append(record)
        if diag.records.count > SimulatedDiagState.ringCapacity { diag.records.removeFirst() }
        if sev >= .warning { diag.active[identity] = record.recID }
        if sev == .latched, !diag.latched.contains(identity) { diag.latched.append(identity) }
        if sev >= .warning { events.append(.diag(record)) }
        if sev.stopsDelivery {
            let bit = entry?.legacyBit ?? 5
            enterFault(V1Transport.faultCode(mask: 1 << UInt16(bit)) ?? .internalError)
        }
        return record
    }

    /// `DIAG_SUMMARY` as the pod would report it.
    public var diagSummary: DiagSummary {
        let all = diag.records
        let activeRecords = diag.active.values.compactMap { id in all.first { $0.recID == id } }
        var summary = DiagSummary(latchedCount: UInt8(diag.latched.count), activeCount: UInt8(activeRecords.count), postState: diag.postState,
                                  nextRecIDLow: UInt16(truncatingIfNeeded: diag.nextID))
        if let top = activeRecords.max(by: { ($0.severity, $0.recID) < ($1.severity, $1.recID) }) {
            let root = DiagChain.root(of: top, in: all)
            summary.topCode = root.code; summary.topSeverityRaw = root.severityRaw; summary.topActionRaw = root.actionRaw; summary.topFruRaw = root.fruRaw
        }
        return summary
    }

    /// `FRU_HEALTH`: unknown until proven, failed / degraded from the ROOT cause's FRU of every active record.
    public var fruHealth: FruHealth {
        var states: [Fru: HealthState] = [:]
        for fru in diag.proven { states[fru] = .ok }
        for id in diag.active.values {
            guard let record = diag.records.first(where: { $0.recID == id }) else { continue }
            let root = DiagChain.root(of: record, in: diag.records)
            guard let fru = root.fru, fru != .none else { continue }
            let state: HealthState = record.severity >= .fault ? .failed : .degraded
            states[fru] = max(states[fru] ?? .unknown, state)
        }
        return FruHealth.pack(states)
    }

    /// Marks FRUs as proven by a passing test (otherwise they stay UNKNOWN, never OK).
    public func markProven(_ frus: [Fru]) { diag.proven.formUnion(frus) }

    /// Test hook: the verification test of this latched code passed, so `ClearDiag` may clear it.
    public func markVerified(_ code: DiagCode) { diag.verified.insert(code.identity) }

    /// `GetFaultLog` semantics: records with id >= `from` (from the oldest when `from` is older), at most `max` per call.
    public func faultLog(from: UInt32, max: Int = 4) -> FaultLog {
        let oldest = diag.records.first?.recID ?? diag.nextID
        let records = diag.records.filter { $0.recID >= Swift.max(from, oldest) }.prefix(Swift.min(Swift.max(max, 1), 4))
        return FaultLog(records: Array(records), latched: diag.latched, nextID: diag.nextID, oldestID: oldest)
    }

    /// `ClearDiag`: `nil` clears every clearable W/F record (latched ones stay). A specific latched code needs its verification.
    public func clearDiag(_ code: DiagCode?) -> Result<DiagSummary, DiagCommandError> {
        func clear(_ identity: DiagCode) {
            guard let id = diag.active.removeValue(forKey: identity), let index = diag.records.firstIndex(where: { $0.recID == id }) else { return }
            diag.records[index].flags.remove(.active)
            let original = diag.records[index]
            diag.latched.removeAll { $0 == identity }
            diag.records.append(DiagRecord(recID: diag.nextID, code: original.code, severityRaw: original.severityRaw, actionRaw: original.actionRaw,
                                           fruRaw: original.fruRaw, fru2Raw: original.fru2Raw, podSeconds: diag.uptimeSeconds,
                                           count: 1, flags: [.cleared, .root]))
            diag.nextID &+= 1
            events.append(.diagCleared(original.code))
        }
        if let code {
            let identity = code.identity
            guard diag.active[identity] != nil else { return .failure(.nack(.invalidState, code: code)) }
            let record = diag.records.first { $0.recID == diag.active[identity] }
            if record?.severity == .latched, !diag.verified.contains(identity) { return .failure(.nack(.notClearable, code: code)) }
            clear(identity)
        } else {
            for identity in Array(diag.active.keys) {
                if let record = diag.records.first(where: { $0.recID == diag.active[identity] }), record.severity != .latched { clear(identity) }
            }
        }
        let stillStopped = diag.active.values.contains { id in diag.records.first { $0.recID == id }?.severity.stopsDelivery == true }
        if !stillStopped { clearLegacyFaultAfterDiag() }
        return .success(diagSummary)
    }

    /// `RunSelfTest`: refused unless the pod is suspended. The simulator "passes" every step of the requested kind.
    public func runSelfTest(_ kind: SelfTestState.Kind) -> Result<SelfTestState, DiagCommandError> {
        guard phase == .suspended || phase == .paired || phase == .filled || phase == .primed else { return .failure(.nack(.selfTestRefused, code: nil)) }
        let steps: UInt16 = kind == .postS ? 0b1_1111_1111_1111 : (kind == .postA ? 0b111_1111_1111 : 0b1)
        if kind == .postS { diag.postState = 1 } else if kind == .postA { diag.postState = 2 }
        events.append(.selfTest(passed: steps, failed: 0))
        return .success(SelfTestState(phaseRaw: SelfTestState.Phase.done.rawValue, kindRaw: kind.rawValue, stepsPassed: steps, stepsFailed: 0))
    }
}
