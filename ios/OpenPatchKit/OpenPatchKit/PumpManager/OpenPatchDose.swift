import Foundation
import HealthKit
import LoopKit

/// A dose that has been commanded but whose end is not yet confirmed. Persisted in the manager state.
struct OpenPatchDose: Codable, Equatable {
    enum Kind: String, Codable { case bolus, tempBasal }

    let kind: Kind
    let id: UInt16               // bolus id on the wire; 0 for temp basals
    let units: Double            // bolus volume, or programmed rate (U/h) for temp basal
    let startDate: Date
    let duration: TimeInterval
    let automatic: Bool
    let insulinType: InsulinType?
    var cancelledAt: Date?
    var deliveredUnitsOverride: Double?

    var scheduledEnd: Date { startDate.addingTimeInterval(duration) }
    var endDate: Date { cancelledAt ?? scheduledEnd }

    func isFinished(at date: Date = Date()) -> Bool { cancelledAt != nil || date >= scheduledEnd }

    /// Estimated delivered insulin at `date` (bolus: linear at 1.5 U/min; temp basal: rate x elapsed).
    func deliveredUnits(at date: Date = Date()) -> Double {
        if let override = deliveredUnitsOverride { return override }
        let end = min(date, endDate)
        let elapsed = max(end.timeIntervalSince(startDate), 0)
        switch kind {
        case .bolus:
            return min(units, units * elapsed / max(duration, 1))
        case .tempBasal:
            return units * elapsed / 3600
        }
    }

    func doseEntry(isMutable: Bool, at date: Date = Date()) -> DoseEntry {
        switch kind {
        case .bolus:
            return DoseEntry(type: .bolus, startDate: startDate, endDate: endDate, value: units, unit: .units,
                             deliveredUnits: isMutable ? nil : deliveredUnits(at: date),
                             insulinType: insulinType, automatic: automatic, isMutable: isMutable)
        case .tempBasal:
            return DoseEntry(type: .tempBasal, startDate: startDate, endDate: endDate, value: units, unit: .unitsPerHour,
                             deliveredUnits: isMutable ? nil : deliveredUnits(at: date),
                             insulinType: insulinType, automatic: automatic, isMutable: isMutable)
        }
    }

    func cancelled(at date: Date, deliveredUnits: Double? = nil) -> OpenPatchDose {
        var copy = self
        copy.cancelledAt = min(max(date, startDate), scheduledEnd)
        copy.deliveredUnitsOverride = deliveredUnits
        return copy
    }

    /// Stable raw identifier -> becomes the dose syncIdentifier. Must be unique per dose and stable across reports.
    var syncRaw: Data {
        var text = "OP-\(kind.rawValue)-\(Int(startDate.timeIntervalSince1970))-\(id)"
        if kind == .tempBasal { text += "-\(units)" }
        return Data(text.utf8)
    }
}

extension NewPumpEvent {
    static func openPatch(dose: OpenPatchDose, isMutable: Bool, at date: Date = Date()) -> NewPumpEvent {
        let title: String
        switch dose.kind {
        case .bolus: title = "Bolus \(dose.units) U"
        case .tempBasal: title = "Temp basal \(dose.units) U/h"
        }
        return NewPumpEvent(date: dose.startDate, dose: dose.doseEntry(isMutable: isMutable, at: date), raw: dose.syncRaw, title: title)
    }

    static func openPatchSuspend(at date: Date) -> NewPumpEvent {
        NewPumpEvent(date: date, dose: DoseEntry(suspendDate: date), raw: Data("OP-suspend-\(Int(date.timeIntervalSince1970))".utf8), title: "Suspend", type: .suspend)
    }

    static func openPatchResume(at date: Date, insulinType: InsulinType?) -> NewPumpEvent {
        NewPumpEvent(date: date, dose: DoseEntry(resumeDate: date, insulinType: insulinType), raw: Data("OP-resume-\(Int(date.timeIntervalSince1970))".utf8), title: "Resume", type: .resume)
    }

    static func openPatchAlarm(at date: Date, type: PumpAlarmType, title: String) -> NewPumpEvent {
        NewPumpEvent(date: date, dose: nil, raw: Data("OP-alarm-\(Int(date.timeIntervalSince1970))-\(title)".utf8), title: title, type: .alarm, alarmType: type)
    }
}
