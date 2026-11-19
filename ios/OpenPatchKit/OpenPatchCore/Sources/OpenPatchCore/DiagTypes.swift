import Foundation

// Diagnostic codes, severity, action and FRU (docs/06-diagnostics.md sections 2.1 to 2.4).
// The catalogue itself (`DiagCatalogue.swift`) is GENERATED from spec/diag-codes.csv by tools/gen_diag.py.

/// 32 bit diagnostic code: `layer(4) | component(8) | fault(12) | inst(8)`. Human notation `L-CC-FFF[/II]` in hex.
public struct DiagCode: Hashable, Comparable, Codable, CustomStringConvertible, Sendable {
    public let raw: UInt32
    public init(raw: UInt32) { self.raw = raw }
    public init(layer: UInt8, component: UInt8, fault: UInt16, inst: UInt8 = 0) {
        self.raw = (UInt32(layer & 0xF) << 28) | (UInt32(component) << 20) | (UInt32(fault & 0xFFF) << 8) | UInt32(inst)
    }
    /// Parses `1-06-001` or `1-06-001/03`.
    public init?(string: String) {
        let halves = string.split(separator: "/", omittingEmptySubsequences: false)
        guard halves.count <= 2 else { return nil }
        let parts = halves[0].split(separator: "-", omittingEmptySubsequences: false)
        guard parts.count == 3, parts[0].count == 1, parts[1].count == 2, parts[2].count == 3,
              let layer = UInt8(parts[0], radix: 16), let component = UInt8(parts[1], radix: 16), let fault = UInt16(parts[2], radix: 16) else { return nil }
        var inst: UInt8 = 0
        if halves.count == 2 {
            guard halves[1].count == 2, let value = UInt8(halves[1], radix: 16) else { return nil }
            inst = value
        }
        self.init(layer: layer, component: component, fault: fault, inst: inst)
    }

    public static let none = DiagCode(raw: 0)

    public var layer: UInt8 { UInt8(raw >> 28) }
    public var component: UInt8 { UInt8((raw >> 20) & 0xFF) }
    public var fault: UInt16 { UInt16((raw >> 8) & 0xFFF) }
    public var inst: UInt8 { UInt8(raw & 0xFF) }
    /// Catalogue identity: the code without its instance qualifier.
    public var identity: DiagCode { DiagCode(raw: raw & 0xFFFF_FF00) }
    public func withInst(_ inst: UInt8) -> DiagCode { DiagCode(raw: (raw & 0xFFFF_FF00) | UInt32(inst)) }
    /// Bits 31..16.
    public var whereBits: UInt16 { UInt16(raw >> 16) }
    /// Bits 15..0.
    public var whatBits: UInt16 { UInt16(raw & 0xFFFF) }

    public var description: String {
        let base = String(format: "%X-%02X-%03X", layer, component, fault)
        return inst == 0 ? base : base + String(format: "/%02X", inst)
    }
    public static func < (a: DiagCode, b: DiagCode) -> Bool { a.raw < b.raw }
}

/// Severity (2.2). Ordered `info < warning < fault < latched`.
public enum DiagSeverity: UInt8, Comparable, CaseIterable, Sendable {
    case info = 0, warning, fault, latched
    public static func < (a: DiagSeverity, b: DiagSeverity) -> Bool { a.rawValue < b.rawValue }
    /// Unknown wire values are a FAULT (an unknown severity is never ignored).
    public init(failsafe raw: UInt8) { self = DiagSeverity(rawValue: raw) ?? .fault }
    /// F and L stop delivery on the pod.
    public var stopsDelivery: Bool { self >= .fault }
}

/// Recommended action (2.3). Raw values are the wire ids.
public enum DiagAction: UInt8, CaseIterable, Sendable {
    case none = 0, retry, ack, refill, redock, recable, rephone, checkPower, replace, reseat
    case swapPod, prime, reprovision, updateFw, reportBug, waitCool, repair, updateApp, checkCannula, isolate
}

/// Field-replaceable unit (2.4). Raw values are the wire ids; ids 19 and up are reserved (Rev B).
public enum Fru: UInt8, CaseIterable, Sendable {
    case none = 0, ctrl, podb, ffc, motor, gear, screw, resv, seal, cap, needle
    case batt, app, magd, mags, usb, cann, fw, chg

    /// User wording of 2.4 (lower case, usable in "Replace the <name>.").
    public var userName: String {
        switch self {
        case .none: return "part"
        case .ctrl: return "controller board"
        case .podb: return "pod sensor board"
        case .ffc: return "FFC cable"
        case .motor: return "motor"
        case .gear: return "gear pair"
        case .screw: return "leadscrew and nut"
        case .resv: return "reservoir"
        case .seal: return "plunger seal"
        case .cap: return "end cap"
        case .needle: return "needle"
        case .batt: return "battery"
        case .app: return "phone app"
        case .magd: return "dock magnet"
        case .mags: return "spindle magnet"
        case .usb: return "USB supply"
        case .cann: return "cannula or infusion set"
        case .fw: return "firmware"
        case .chg: return "charger"
        }
    }
}

/// One generated catalogue row.
public struct DiagCatalogueEntry: Equatable, Sendable {
    /// Instance 0.
    public let code: DiagCode
    public let name: String
    public let severity: DiagSeverity
    public let action: DiagAction
    public let fru: Fru
    public let fru2: Fru?
    /// Legacy `FAULT_MASK` bit 0...7 for F and L codes (2.7), `nil` for I and W.
    public let legacyBit: Int?
    /// Bit n = hazard Hn.
    public let hazards: UInt16
    /// The Trio text (English, at most 90 characters); the app appends the action sentence and the code.
    public let text: String

    public init(code: DiagCode, name: String, severity: DiagSeverity, action: DiagAction, fru: Fru, fru2: Fru?,
                legacyBit: Int?, hazards: UInt16, text: String) {
        self.code = code; self.name = name; self.severity = severity; self.action = action; self.fru = fru
        self.fru2 = fru2; self.legacyBit = legacyBit; self.hazards = hazards; self.text = text
    }
}

/// Lookup in the generated catalogue (by catalogue identity, the instance is ignored).
public enum DiagCatalogue {
    public static var schemaVersion: UInt16 { DiagCatalogueData.schemaVersion }
    public static var entries: [DiagCatalogueEntry] { DiagCatalogueData.entries }
    private static let index: [UInt32: DiagCatalogueEntry] = {
        Dictionary(DiagCatalogueData.entries.map { ($0.code.raw, $0) }, uniquingKeysWith: { first, _ in first })
    }()

    public static func lookup(_ code: DiagCode) -> DiagCatalogueEntry? { index[code.identity.raw] }
}
