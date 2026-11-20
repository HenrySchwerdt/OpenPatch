import XCTest
@testable import OpenPatchCore

/// Trio-facing text, root-cause rule, forward compatibility (docs/06-diagnostics.md 5.6): table-driven over every catalogue row.
final class DiagPresentationTests: XCTestCase {
    private func record(for entry: DiagCatalogueEntry, id: UInt32 = 1) -> DiagRecord {
        DiagRecord(recID: id, code: entry.code, severityRaw: entry.severity.rawValue, actionRaw: entry.action.rawValue, fruRaw: entry.fru.rawValue,
                   fru2Raw: entry.fru2?.rawValue ?? 0, flags: entry.severity >= .warning ? [.active, .root] : [.root])
    }

    func testTheDocumentedExample() {
        let entry = DiagCatalogue.lookup(.vmotStuckOn)!
        let r = DiagResolver.resolve(record(for: entry))
        XCTAssertFalse(r.isUnknown)
        XCTAssertEqual(r.name, "VMOT_STUCK_ON")
        XCTAssertEqual(DiagText.message(for: r), "Motor supply stuck on. Replace the controller board. Code 1-06-001.")
        let plan = DiagText.plan(for: record(for: entry), podName: "Pod A", role: "A")
        XCTAssertEqual(plan.identifier, "diag-1-06-001-A")
        XCTAssertEqual(plan.title, "Pod A: Controller board")
        XCTAssertEqual(plan.body, "Motor supply stuck on. Replace the controller board. Code 1-06-001. Delivery is stopped; swap to the other pod.")
        XCTAssertEqual(plan.interruption, .critical)
        XCTAssertEqual(plan.repeatInterval, 900)
        XCTAssertTrue(plan.stopsDelivery)
    }

    func testActionSentences() {
        XCTAssertEqual(DiagText.actionSentence(.recable, fru: .ffc), "Reconnect the FFC cable.")
        XCTAssertEqual(DiagText.actionSentence(.refill, fru: .none), "Refill the pod.")
        XCTAssertEqual(DiagText.actionSentence(.isolate, fru: .podb), "Open Pump settings, Component health, to find the faulty part.")
        XCTAssertEqual(DiagText.actionSentence(.reportBug, fru: .fw), "This should never happen. Export the diagnostic report and contact the project.")
        XCTAssertEqual(DiagText.actionSentence(.replace, fru: .motor), "Replace the motor.")
        XCTAssertNil(DiagText.actionSentence(.none, fru: .none))
        for action in DiagAction.allCases where action != .none {
            XCTAssertNotNil(DiagText.actionSentence(action, fru: .ctrl), "\(action)")
        }
        XCTAssertEqual(DiagText.humanName("MOTOR_LEAD_OPEN"), "Motor lead open")
        XCTAssertEqual(DiagText.fruTitle(.ffc), "FFC cable")
    }

    /// Every catalogue row: identifier, title, body (contains the text, the FRU instruction and the code), level, repeat trigger.
    func testEveryCatalogueRowMapsToExactlyOneWellFormedAlert() {
        var identifiers = Set<String>()
        for entry in DiagCatalogue.entries {
            let rec = record(for: entry)
            let plan = DiagText.plan(for: rec, podName: "Pod B", role: "B")
            let name = entry.code.description
            XCTAssertEqual(plan.identifier, "diag-\(name)-B")
            XCTAssertTrue(identifiers.insert(plan.identifier).inserted, "one alert per (pod, code): \(name)")
            XCTAssertTrue(plan.title.hasPrefix("Pod B: "), name)
            XCTAssertTrue(plan.body.contains(entry.text), name)
            XCTAssertTrue(plan.body.contains("Code \(name)."), name)
            if let sentence = DiagText.actionSentence(entry.action, fru: entry.fru) { XCTAssertTrue(plan.body.contains(sentence), name) }
            if entry.action == .replace { XCTAssertTrue(plan.body.contains("Replace the \(entry.fru.userName)."), name) }
            switch entry.severity {
            case .info: XCTAssertEqual(plan.interruption, .none, name)
            case .warning: XCTAssertEqual(plan.interruption, .timeSensitive, name)
            case .fault, .latched: XCTAssertEqual(plan.interruption, .critical, name)
            }
            XCTAssertEqual(plan.repeatInterval != nil, entry.severity == .latched, name)
            XCTAssertEqual(plan.stopsDelivery, entry.severity.stopsDelivery, name)
            XCTAssertEqual(plan.body.contains("Delivery is stopped"), entry.severity.stopsDelivery, name)
            XCTAssertLessThan(plan.body.count, 260, "\(name): alert body too long")
        }
        XCTAssertEqual(identifiers.count, 155)
    }

    // MARK: Forward compatibility

    func testUnknownCodeIsTreatedAsAFaultWithTheRecordsOwnValues() {
        let unknown = DiagCode(raw: 0x1FFF_FF00)
        XCTAssertNil(DiagCatalogue.lookup(unknown))
        let rec = DiagRecord(recID: 9, code: unknown, severityRaw: 2, actionRaw: DiagAction.replace.rawValue, fruRaw: Fru.motor.rawValue, flags: [.active, .root])
        let r = DiagResolver.resolve(rec)
        XCTAssertTrue(r.isUnknown)
        XCTAssertEqual(r.severity, .fault)
        XCTAssertEqual(r.fru, .motor, "the record's own FRU")
        XCTAssertEqual(r.action, .replace)
        XCTAssertEqual(DiagText.message(for: r), "Code 0x1FFFFF00 (severity 2). Update the app.")
        let plan = DiagText.plan(for: rec, podName: "Pod A", role: "A")
        XCTAssertEqual(plan.title, "Unknown pod error")
        XCTAssertEqual(plan.interruption, .critical)
        XCTAssertTrue(plan.stopsDelivery)
        XCTAssertEqual(plan.identifier, "diag-1-FF-FFF-A")
    }

    func testUnknownSeverityByteOfAnUnknownCodeIsStillAFault() {
        let rec = DiagRecord(recID: 1, code: DiagCode(raw: 0x1FFF_FF00), severityRaw: 77, actionRaw: 200, fruRaw: 99)
        let r = DiagResolver.resolve(rec)
        XCTAssertEqual(r.severity, .fault)
        XCTAssertEqual(r.action, .reportBug, "unknown action falls back to report")
        XCTAssertEqual(r.fru, .fw)
        XCTAssertTrue(DiagText.plan(for: rec, podName: "Pod A", role: "A").stopsDelivery)
    }

    func testTheRecordWinsOverTheCatalogueWhenTheyDisagree() {
        // an app older than the pod: the pod already moved this code from LATCHED to WARNING and from REPLACE to RETRY
        let entry = DiagCatalogue.lookup(.vmotStuckOn)!
        var rec = record(for: entry)
        rec.severityRaw = DiagSeverity.warning.rawValue
        rec.actionRaw = DiagAction.retry.rawValue
        rec.fruRaw = Fru.motor.rawValue
        let r = DiagResolver.resolve(rec)
        XCTAssertEqual(r.severity, .warning)
        XCTAssertEqual(r.action, .retry)
        XCTAssertEqual(r.fru, .motor)
        XCTAssertEqual(r.text, entry.text, "the text comes from the app's catalogue")
        let plan = DiagText.plan(for: rec, podName: "Pod A", role: "A")
        XCTAssertEqual(plan.interruption, .timeSensitive)
        XCTAssertNil(plan.repeatInterval)
        XCTAssertFalse(plan.stopsDelivery)
    }

    func testNonHardwareCodesUseTheCatalogueNameInTheTitle() {
        let entry = DiagCatalogue.lookup(.reservoirEmpty)!
        XCTAssertEqual(DiagText.plan(for: record(for: entry), podName: "Pod A", role: "A").title, "Pod A: Reservoir empty")
        let boot = DiagCatalogue.lookup(.boot)!
        XCTAssertEqual(DiagText.plan(for: record(for: boot), podName: "Pod A", role: "A").interruption, .none)
    }
}
