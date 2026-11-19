import XCTest
@testable import OpenPatchCore

/// Catalogue integrity (docs/06-diagnostics.md 2.8, 6.1): the generated Swift catalogue equals spec/diag-codes.csv.
final class DiagCatalogueTests: XCTestCase {
    func testCatalogueHas150CodesWithTheDocumentedSeveritySplit() {
        let entries = DiagCatalogue.entries
        XCTAssertEqual(entries.count, 150)
        func count(_ s: DiagSeverity) -> Int { entries.filter { $0.severity == s }.count }
        XCTAssertEqual([count(.info), count(.warning), count(.fault), count(.latched)], [2, 54, 68, 26])
        XCTAssertEqual(DiagCatalogue.schemaVersion, 1)
    }

    func testSortedUniqueAndInstanceFree() {
        let entries = DiagCatalogue.entries
        XCTAssertEqual(entries.map(\.code), entries.map(\.code).sorted())
        XCTAssertEqual(Set(entries.map(\.code)).count, entries.count)
        XCTAssertEqual(Set(entries.map(\.name)).count, entries.count)
        for e in entries {
            XCTAssertEqual(e.code.inst, 0)
            XCTAssertEqual(DiagCatalogue.lookup(e.code), e)
            XCTAssertEqual(DiagCatalogue.lookup(e.code.withInst(9)), e, "lookup ignores the instance")
            XCTAssertLessThanOrEqual(e.text.count, 90, e.code.description)
            XCTAssertFalse(e.text.isEmpty)
            XCTAssertEqual(e.legacyBit != nil, e.severity.stopsDelivery, "only F and L project to a legacy bit: \(e.code)")
        }
    }

    func testConstantsAndNotation() {
        XCTAssertEqual(DiagCode.vmotStuckOn.raw, 0x1060_0100, "worked example of 5.4")
        XCTAssertEqual(DiagCode.vmotStuckOn.description, "1-06-001")
        XCTAssertEqual(DiagCode.vmotStuckOn.withInst(3).description, "1-06-001/03")
        XCTAssertEqual(DiagCode.lfxoNotRunning.description, "1-0B-001")
        XCTAssertEqual(DiagCode(string: "1-06-001/03"), DiagCode.vmotStuckOn.withInst(3))
        XCTAssertEqual(DiagCode(string: "A-A0-002"), DiagCode.batteryCritical)
        XCTAssertNil(DiagCode(string: "1-6-001"))
        XCTAssertNil(DiagCode(string: "G-06-001"))
        XCTAssertNil(DiagCode(string: "1-06-001/3"))
        XCTAssertEqual(DiagCode.vmotStuckOn.whereBits, 0x1060)
        XCTAssertEqual(DiagCode.vmotStuckOn.whatBits, 0x0100)
        let e = DiagCatalogue.lookup(.vmotStuckOn)
        XCTAssertEqual(e?.severity, .latched)
        XCTAssertEqual(e?.fru, .ctrl)
        XCTAssertEqual(e?.action, .replace)
        XCTAssertEqual(e?.legacyBit, 5)
        XCTAssertEqual(e?.text, "Motor supply stuck on.")
        XCTAssertEqual(DiagCatalogue.lookup(.batteryCritical)?.legacyBit, 3)
        XCTAssertEqual(DiagCatalogue.lookup(.wearExpired)?.legacyBit, 7)
        XCTAssertEqual(DiagCatalogue.lookup(.usbSupplyLow)?.fru2, nil)
        XCTAssertEqual(DiagCatalogue.lookup(.motorLeadOpen)?.fru, .motor)
        XCTAssertNil(DiagCatalogue.lookup(DiagCode(raw: 0x1FFF_FF00)))
    }

    func testUnknownSeverityIsAFault() {
        XCTAssertEqual(DiagSeverity(failsafe: 9), .fault)
        XCTAssertEqual(DiagSeverity(failsafe: 0), .info)
        XCTAssertTrue(DiagSeverity.latched.stopsDelivery)
        XCTAssertFalse(DiagSeverity.warning.stopsDelivery)
    }

    // MARK: spec/diag-codes.csv is the source of truth

    private func parseCSV(_ text: String) -> [[String]] {
        var rows: [[String]] = [], row: [String] = [], cell = "", quoted = false
        var chars = Array(text.unicodeScalars)[...]
        while let c = chars.popFirst() {
            switch (quoted, c) {
            case (true, "\""):
                if chars.first == "\"" { cell.unicodeScalars.append("\""); chars.removeFirst() } else { quoted = false }
            case (true, _): cell.unicodeScalars.append(c)
            case (false, "\""): quoted = true
            case (false, ","): row.append(cell); cell = ""
            case (false, "\n"): row.append(cell); cell = ""; rows.append(row); row = []
            case (false, _): cell.unicodeScalars.append(c)
            }
        }
        return rows
    }

    func testMatchesTheCSV() throws {
        // .../ios/OpenPatchKit/OpenPatchCore/Tests/OpenPatchCoreTests/<this file> -> repo root is 5 levels up
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<6 { url.deleteLastPathComponent() }
        let csvURL = url.appendingPathComponent("spec/diag-codes.csv")
        let text = try String(contentsOf: csvURL, encoding: .utf8)
        let rows = parseCSV(text)
        let head = rows[0]
        func col(_ name: String) -> Int { head.firstIndex(of: name)! }
        let entries = DiagCatalogue.entries
        XCTAssertEqual(rows.count - 1, entries.count)
        for (r, e) in zip(rows.dropFirst(), entries) {
            XCTAssertEqual(DiagCode(string: r[col("code")]), e.code)
            XCTAssertEqual(r[col("name")], e.name)
            XCTAssertEqual(r[col("text")], e.text)
            XCTAssertEqual(["I": DiagSeverity.info, "W": .warning, "F": .fault, "L": .latched][r[col("sev")]], e.severity, e.code.description)
            XCTAssertEqual(Int(r[col("legacy_bit")]), e.legacyBit, e.code.description)
            XCTAssertEqual(r[col("fru")].lowercased(), String(describing: e.fru), e.code.description)
            XCTAssertEqual(r[col("fru2")].isEmpty ? nil : r[col("fru2")].lowercased(), e.fru2.map { String(describing: $0) }, e.code.description)
            var mask: UInt16 = 0
            for h in r[col("haz")].split(separator: " ") { mask |= 1 << UInt16(h.dropFirst())! }
            XCTAssertEqual(mask, e.hazards, e.code.description)
        }
    }
}
