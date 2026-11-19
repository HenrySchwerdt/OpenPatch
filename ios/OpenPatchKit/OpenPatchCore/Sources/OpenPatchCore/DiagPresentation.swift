import Foundation

// What a record means to the user (docs/06-diagnostics.md 5.6): the catalogue lookup, the forward compatible fallback for unknown
// codes and the Trio-facing text. Pure: LoopKit alerts are built from this in OpenPatchKit (WP-6).

/// A record together with its catalogue row. The record wins where both disagree (an app older or newer than the pod): "the
/// record's severity, action and FRU win".
public struct DiagResolved: Equatable, Sendable {
    public var record: DiagRecord
    /// `nil` = the code is not in this app's catalogue (`9-95-002 UNKNOWN_POD_CODE`): treated as a fault with the record's own
    /// severity, FRU and action, the raw code is shown.
    public var entry: DiagCatalogueEntry?
    public var severity: DiagSeverity
    public var action: DiagAction
    public var fru: Fru
    public var fru2: Fru?

    public var code: DiagCode { record.code }
    public var isUnknown: Bool { entry == nil }
    /// The English catalogue text; for an unknown code the generic title.
    public var text: String { entry?.text ?? DiagText.unknownTitle }
    /// Short name of the catalogue row (`VMOT_STUCK_ON`), `nil` when unknown.
    public var name: String? { entry?.name }
}

public enum DiagResolver {
    public static func resolve(_ record: DiagRecord) -> DiagResolved {
        let entry = DiagCatalogue.lookup(record.code)
        // unknown enum values in the record fall back to the catalogue row, then to a safe default
        let action = record.action ?? entry?.action ?? .reportBug
        let fru = record.fru ?? entry?.fru ?? .fw
        return DiagResolved(record: record, entry: entry, severity: record.severity, action: action, fru: fru, fru2: record.fru2)
    }
}

/// Alert level of a record (5.6), mapped to a LoopKit `Alert.InterruptionLevel` by the kit.
public enum DiagInterruption: Equatable, Sendable {
    /// Information: no alert, shown only in the log view and the report.
    case none
    case timeSensitive
    case critical
}

/// Everything an alert for one record needs, without LoopKit.
public struct DiagAlertPlan: Equatable, Sendable {
    /// `diag-<L-CC-FFF>-<role>`, stable per code and pod, so alerts can be de-duplicated and retracted.
    public var identifier: String
    public var title: String
    public var body: String
    public var interruption: DiagInterruption
    /// 15 minutes for latched codes ("repeats until the latched code is cleared by its verification test").
    public var repeatInterval: TimeInterval?
    public var stopsDelivery: Bool
}

public enum DiagText {
    public static let unknownTitle = "Unknown pod error"

    /// FRU wording of 2.4 with a capital letter ("Controller board"), for titles.
    public static func fruTitle(_ fru: Fru) -> String {
        let name = fru.userName
        return name.prefix(1).uppercased() + name.dropFirst()
    }

    /// "MOTOR_LEAD_OPEN" -> "Motor lead open".
    public static func humanName(_ name: String) -> String {
        let words = name.lowercased().replacingOccurrences(of: "_", with: " ")
        return words.prefix(1).uppercased() + words.dropFirst()
    }

    /// The action sentence (5.6). `nil` for NONE.
    public static func actionSentence(_ action: DiagAction, fru: Fru) -> String? {
        switch action {
        case .none: return nil
        case .retry: return "Try again."
        case .ack: return "Acknowledge the alert, then resume."
        case .refill: return "Refill the pod."
        case .redock: return "Take the pod off and dock it again."
        case .recable: return "Reconnect the FFC cable."
        case .rephone: return "Bring the phone closer or restart Bluetooth."
        case .checkPower: return "Check the USB supply and cable."
        case .replace: return "Replace the \(fru.userName)."
        case .reseat: return "Reseat the \(fru.userName), then run the self-test."
        case .swapPod: return "Switch to the other pod."
        case .prime: return "Prime before resuming."
        case .reprovision: return "Re-provision the pod with the programmer."
        case .updateFw: return "Update the pod firmware."
        case .reportBug: return "This should never happen. Export the diagnostic report and contact the project."
        case .waitCool: return "Let the pod cool down or warm up."
        case .repair: return "Pair the pod again."
        case .updateApp: return "Update the app."
        case .checkCannula: return "Check the cannula and infusion set."
        case .isolate: return "Open Pump settings, Component health, to find the faulty part."
        }
    }

    /// The Trio-facing sentence: `"<text> <action sentence> Code L-CC-FFF."`, for example
    /// `"Motor supply stuck on. Replace the controller board. Code 1-06-001."`. An unknown code reads
    /// `"Code 0x%08X (severity N). Update the app."` with the record's own severity.
    public static func message(for resolved: DiagResolved) -> String {
        if resolved.isUnknown {
            return String(format: "Code 0x%08X (severity %d). Update the app.", resolved.code.raw, Int(resolved.severity.rawValue))
        }
        var parts = [resolved.text]
        if let sentence = actionSentence(resolved.action, fru: resolved.fru) { parts.append(sentence) }
        parts.append("Code \(resolved.code.identity).")
        return parts.joined(separator: " ")
    }

    /// What happens to delivery, appended to alert bodies for F and L records.
    public static func deliveryNote(_ severity: DiagSeverity) -> String? {
        switch severity {
        case .info, .warning: return nil
        case .fault: return "Delivery is stopped."
        case .latched: return "Delivery is stopped; swap to the other pod."
        }
    }

    /// The alert for a record (root cause rule: pass the ROOT record of the chain). `podName` is "Pod A".
    public static func plan(for record: DiagRecord, podName: String, role: String) -> DiagAlertPlan {
        let r = DiagResolver.resolve(record)
        let hardware: Set<Fru> = [.ctrl, .podb, .ffc, .motor, .gear, .screw, .resv, .seal, .cap, .needle, .batt, .magd, .mags, .usb, .cann, .chg]
        let title: String
        if r.isUnknown { title = DiagText.unknownTitle }
        else if hardware.contains(r.fru) { title = "\(podName): \(fruTitle(r.fru))" }
        else { title = "\(podName): \(humanName(r.name ?? r.code.description))" }
        var body = message(for: r)
        if !r.isUnknown, let note = deliveryNote(r.severity) { body += " " + note }
        let level: DiagInterruption
        switch r.severity {
        case .info: level = .none
        case .warning: level = .timeSensitive
        case .fault, .latched: level = .critical
        }
        return DiagAlertPlan(identifier: "diag-\(r.code.identity)-\(role)", title: title, body: body, interruption: level,
                             repeatInterval: r.severity == .latched ? 15 * 60 : nil, stopsDelivery: r.severity.stopsDelivery)
    }
}
