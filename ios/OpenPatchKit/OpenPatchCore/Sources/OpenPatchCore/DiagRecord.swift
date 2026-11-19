import Foundation

// Diagnostic records, summary and FRU health as the pod reports them (docs/06-diagnostics.md 2.6, 5.4, 5.5).

/// The 32 byte diagnostic record (2.6), little endian on the wire. Enumerations stay as raw bytes so that a record from a
/// newer pod is kept verbatim; the typed accessors map unknown values fail-safe (an unknown severity is a FAULT).
public struct DiagRecord: Equatable, Sendable {
    public static let byteCount = 32

    public struct Flags: OptionSet, Sendable {
        public let rawValue: UInt8
        public init(rawValue: UInt8) { self.rawValue = rawValue }
        public static let latched = Flags(rawValue: 1 << 0)
        /// The condition is still present.
        public static let active = Flags(rawValue: 1 << 1)
        public static let escalated = Flags(rawValue: 1 << 2)
        public static let firstSinceBoot = Flags(rawValue: 1 << 3)
        public static let duringPOST = Flags(rawValue: 1 << 4)
        /// Clear record: the condition of `causeRec` is gone.
        public static let cleared = Flags(rawValue: 1 << 5)
        /// No `causeRec`: a root cause.
        public static let root = Flags(rawValue: 1 << 6)
    }

    public var recID: UInt32
    public var code: DiagCode
    public var severityRaw: UInt8
    public var actionRaw: UInt8
    public var fruRaw: UInt8
    public var fru2Raw: UInt8
    /// Seconds since the pod booted.
    public var podSeconds: UInt32
    /// Measured value (unit per code, see the catalogue).
    public var ctxA: Int32
    /// Threshold or expected value.
    public var ctxB: Int32
    /// Cumulative step count at the event or an angle count.
    public var ctxC: UInt32
    /// Occurrences coalesced into this record (saturates at 255).
    public var count: UInt8
    public var flags: Flags
    /// Low 16 bits of the `recID` of the record that caused this one, 0 = this is a root.
    public var causeRec: UInt16

    public init(recID: UInt32, code: DiagCode, severityRaw: UInt8, actionRaw: UInt8, fruRaw: UInt8, fru2Raw: UInt8 = 0,
                podSeconds: UInt32 = 0, ctxA: Int32 = 0, ctxB: Int32 = 0, ctxC: UInt32 = 0, count: UInt8 = 1,
                flags: Flags = [], causeRec: UInt16 = 0) {
        self.recID = recID; self.code = code; self.severityRaw = severityRaw; self.actionRaw = actionRaw
        self.fruRaw = fruRaw; self.fru2Raw = fru2Raw; self.podSeconds = podSeconds
        self.ctxA = ctxA; self.ctxB = ctxB; self.ctxC = ctxC; self.count = count; self.flags = flags; self.causeRec = causeRec
    }

    /// Decodes exactly 32 bytes; every byte pattern of that length is a record.
    public init?(bytes: [UInt8]) {
        guard bytes.count == Self.byteCount else { return nil }
        var r = ByteReader(bytes)
        guard let recID = try? r.u32(), let code = try? r.u32(), let sev = try? r.u8(), let act = try? r.u8(), let fru = try? r.u8(),
              let fru2 = try? r.u8(), let t = try? r.u32(), let a = try? r.i32(), let b = try? r.i32(), let c = try? r.u32(),
              let count = try? r.u8(), let flags = try? r.u8(), let cause = try? r.u16() else { return nil }
        self.init(recID: recID, code: DiagCode(raw: code), severityRaw: sev, actionRaw: act, fruRaw: fru, fru2Raw: fru2, podSeconds: t,
                  ctxA: a, ctxB: b, ctxC: c, count: count, flags: Flags(rawValue: flags), causeRec: cause)
    }

    public var bytes: [UInt8] {
        var w = ByteWriter()
        w.u32(recID); w.u32(code.raw); w.u8(severityRaw); w.u8(actionRaw); w.u8(fruRaw); w.u8(fru2Raw)
        w.u32(podSeconds); w.i32(ctxA); w.i32(ctxB); w.u32(ctxC); w.u8(count); w.u8(flags.rawValue); w.u16(causeRec)
        return w.bytes
    }

    /// Fail-safe: an unknown severity value is a FAULT.
    public var severity: DiagSeverity { DiagSeverity(failsafe: severityRaw) }
    public var action: DiagAction? { DiagAction(rawValue: actionRaw) }
    public var fru: Fru? { Fru(rawValue: fruRaw) }
    /// Secondary suspect, `nil` for none (or an unknown id).
    public var fru2: Fru? { fru2Raw == 0 ? nil : Fru(rawValue: fru2Raw) }
    public var isRoot: Bool { causeRec == 0 }
    public var isActive: Bool { flags.contains(.active) }
    public var isLatched: Bool { flags.contains(.latched) }
    public var isClearRecord: Bool { flags.contains(.cleared) }
}

/// Cause chain helpers (docs/06-diagnostics.md 1.6): the headline of a chain is its root, the chain goes in the details.
public enum DiagChain {
    /// Maximum chain depth.
    public static let maxDepth = 4

    /// The chain from `record` down to its root, following `causeRec` through `records` (matched on the low 16 bits of the
    /// record id, newest first). `missingCause` is true when the walk ended at a cause that is not in `records`
    /// ("cause not in log").
    public static func chain(from record: DiagRecord, in records: [DiagRecord]) -> (records: [DiagRecord], missingCause: Bool) {
        var chain = [record]
        var current = record
        while current.causeRec != 0, chain.count < maxDepth {
            guard let cause = records.last(where: { UInt16(truncatingIfNeeded: $0.recID) == current.causeRec && $0.recID != current.recID }) else {
                return (chain, true)
            }
            chain.append(cause)
            current = cause
        }
        return (chain, false)
    }

    /// The root record (or the deepest one that could be found).
    public static func root(of record: DiagRecord, in records: [DiagRecord]) -> DiagRecord {
        chain(from: record, in: records).records.last ?? record
    }
}

/// `DIAG_SUMMARY` (tag 0x27, 14 bytes): the headline of a pod's diagnostic state.
public struct DiagSummary: Equatable, Sendable {
    public static let byteCount = 14
    /// Root code of the most severe active record, `nil` = none.
    public var topCode: DiagCode?
    public var topSeverityRaw: UInt8
    public var topActionRaw: UInt8
    public var topFruRaw: UInt8
    public var latchedCount: UInt8
    /// Active W/F/L records.
    public var activeCount: UInt8
    /// 0 not run, 1 S passed, 2 A passed, 3 S failed, 4 A failed, 5 running.
    public var postState: UInt8
    /// Low 16 bits of the next record id: when it moves, the app pulls `GetFaultLog`.
    public var nextRecIDLow: UInt16
    /// Catalogue version of the pod.
    public var schema: UInt16

    public init(topCode: DiagCode? = nil, topSeverityRaw: UInt8 = 0, topActionRaw: UInt8 = 0, topFruRaw: UInt8 = 0, latchedCount: UInt8 = 0,
                activeCount: UInt8 = 0, postState: UInt8 = 0, nextRecIDLow: UInt16 = 1, schema: UInt16 = DiagCatalogue.schemaVersion) {
        self.topCode = topCode; self.topSeverityRaw = topSeverityRaw; self.topActionRaw = topActionRaw; self.topFruRaw = topFruRaw
        self.latchedCount = latchedCount; self.activeCount = activeCount; self.postState = postState
        self.nextRecIDLow = nextRecIDLow; self.schema = schema
    }

    public init?(bytes: [UInt8]) {
        guard bytes.count == Self.byteCount else { return nil }
        var r = ByteReader(bytes)
        guard let code = try? r.u32(), let sev = try? r.u8(), let act = try? r.u8(), let fru = try? r.u8(), let nl = try? r.u8(),
              let na = try? r.u8(), let post = try? r.u8(), let next = try? r.u16(), let schema = try? r.u16() else { return nil }
        self.init(topCode: code == 0 ? nil : DiagCode(raw: code), topSeverityRaw: sev, topActionRaw: act, topFruRaw: fru, latchedCount: nl,
                  activeCount: na, postState: post, nextRecIDLow: next, schema: schema)
    }

    public var bytes: [UInt8] {
        var w = ByteWriter()
        w.u32(topCode?.raw ?? 0); w.u8(topSeverityRaw); w.u8(topActionRaw); w.u8(topFruRaw); w.u8(latchedCount); w.u8(activeCount)
        w.u8(postState); w.u16(nextRecIDLow); w.u16(schema)
        return w.bytes
    }

    public var topSeverity: DiagSeverity { DiagSeverity(failsafe: topSeverityRaw) }
    public var topAction: DiagAction? { DiagAction(rawValue: topActionRaw) }
    public var topFru: Fru? { Fru(rawValue: topFruRaw) }
    /// `true` when the pod runs another catalogue than this app (a newer or older one): records still carry everything needed.
    public var schemaDiffers: Bool { schema != DiagCatalogue.schemaVersion }
}

/// Health of one FRU (`FRU_HEALTH`, 2 bits per FRU id).
public enum HealthState: UInt8, Comparable, Sendable {
    /// Not proven: never shown as OK.
    case unknown = 0
    case ok = 1
    /// A warning is active.
    case degraded = 2
    /// A fault or latched record is active.
    case failed = 3
    public static func < (a: HealthState, b: HealthState) -> Bool { a.rawValue < b.rawValue }
}

public struct FruHealth: Equatable, Sendable {
    public var raw: UInt64
    public init(raw: UInt64) { self.raw = raw }
    public func state(of fru: Fru) -> HealthState { HealthState(rawValue: UInt8((raw >> (2 * UInt64(fru.rawValue))) & 3)) ?? .unknown }
    /// Every FRU of the catalogue that exists in this build, with its state.
    public var states: [Fru: HealthState] { Dictionary(uniqueKeysWithValues: Fru.allCases.map { ($0, state(of: $0)) }) }
    public static func pack(_ states: [Fru: HealthState]) -> FruHealth {
        var raw: UInt64 = 0
        for (fru, state) in states { raw |= UInt64(state.rawValue) << (2 * UInt64(fru.rawValue)) }
        return FruHealth(raw: raw)
    }
}

/// Stable identity of a pod (`POD_UID`, nRF `FICR.DEVICEID`), independent of its role A/B.
public struct PodUID: Hashable, Codable, CustomStringConvertible, Sendable {
    public let raw: UInt64
    public init(raw: UInt64) { self.raw = raw }
    public var description: String { String(format: "%016llx", raw) }
}

/// `SELFTEST_STATE` (tag 0x2D).
public struct SelfTestState: Equatable, Sendable {
    public enum Phase: UInt8, Sendable { case idle = 0, running, done }
    public enum Kind: UInt8, Sendable { case postS = 1, postA, watchdog }
    public var phaseRaw: UInt8
    public var kindRaw: UInt8
    public var stepsPassed: UInt16
    public var stepsFailed: UInt16
    public init(phaseRaw: UInt8 = 0, kindRaw: UInt8 = 0, stepsPassed: UInt16 = 0, stepsFailed: UInt16 = 0) {
        self.phaseRaw = phaseRaw; self.kindRaw = kindRaw; self.stepsPassed = stepsPassed; self.stepsFailed = stepsFailed
    }
    public var phase: Phase? { Phase(rawValue: phaseRaw) }
    public var kind: Kind? { Kind(rawValue: kindRaw) }
}

/// The answer to `GetFaultLog` (all pages).
public struct FaultLog: Equatable, Sendable {
    public var records: [DiagRecord]
    /// Codes of the pod's latched set.
    public var latched: [DiagCode]
    public var nextID: UInt32
    public var oldestID: UInt32
    public init(records: [DiagRecord] = [], latched: [DiagCode] = [], nextID: UInt32 = 1, oldestID: UInt32 = 1) {
        self.records = records; self.latched = latched; self.nextID = nextID; self.oldestID = oldestID
    }
}

/// Why a diagnostic command did not succeed.
public enum DiagCommandError: Error, Equatable {
    case transport(TransportError)
    /// The pod refused (`selfTestRefused`, `latched`, `notClearable`, ...); `code` is the `DIAG_CODE` it named, if any.
    case nack(NackReason, code: DiagCode?)
}
