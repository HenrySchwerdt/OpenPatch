import XCTest
@testable import OpenPatchCore

/// The numbers of the wire protocol are written twice: in `firmware-rs` (Rust, the pod) and here (Swift, the phone). This suite
/// reads the Rust source files and compares every command id, TLV tag, state flag, result code, history event, fault bit and drive
/// preset with the Swift tables, so a drift on either side fails the build instead of showing up on the bench.
final class FirmwareParityTests: XCTestCase {
    private func rust(_ path: String) throws -> String {
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<6 { url.deleteLastPathComponent() }
        return try String(contentsOf: url.appendingPathComponent("firmware-rs/" + path), encoding: .utf8)
    }

    /// `NAME_WITH_UNDERSCORES` and `nameWithUnderscores` meet at "namewithunderscores".
    private func normalized(_ name: String) -> String { name.replacingOccurrences(of: "_", with: "").lowercased() }

    private func number(_ expression: String) -> Int? {
        let e = expression.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "_", with: "")
        if e.hasPrefix("0x") { return Int(e.dropFirst(2), radix: 16) }
        if let shift = e.range(of: "<<") {
            guard let l = Int(e[..<shift.lowerBound].trimmingCharacters(in: .whitespaces)), let r = Int(e[shift.upperBound...].trimmingCharacters(in: .whitespaces)) else { return nil }
            return l << r
        }
        return Int(e)
    }

    /// `pub const NAME: u8 = 0x01;` inside `pub mod <name> { ... }`.
    private func constants(inModule module: String, of source: String) throws -> [String: Int] {
        let start = try XCTUnwrap(source.range(of: "pub mod \(module) {"), "module \(module)")
        let rest = source[start.upperBound...]
        let end = try XCTUnwrap(rest.range(of: "\n}\n"))
        let body = String(rest[..<end.lowerBound])
        let regex = try NSRegularExpression(pattern: #"pub const ([A-Z0-9_]+): (?:u8|u16|u32) = ([^;]+);"#)
        var out: [String: Int] = [:]
        for m in regex.matches(in: body, range: NSRange(body.startIndex..., in: body)) {
            let name = String(body[Range(m.range(at: 1), in: body)!])
            if let value = number(String(body[Range(m.range(at: 2), in: body)!])) { out[name] = value }
        }
        return out
    }

    /// `Name = 12,` lines of an enum.
    private func enumValues(_ enumName: String, of source: String) throws -> [String: Int] {
        let start = try XCTUnwrap(source.range(of: "pub enum \(enumName) {"), enumName)
        let rest = source[start.upperBound...]
        let body = String(rest[..<(try XCTUnwrap(rest.range(of: "\n}\n"))).lowerBound])
        let regex = try NSRegularExpression(pattern: #"^\s*([A-Z][A-Za-z0-9_]*) = ([0-9xXa-fA-F_]+),"#, options: .anchorsMatchLines)
        var out: [String: Int] = [:]
        for m in regex.matches(in: body, range: NSRange(body.startIndex..., in: body)) {
            if let v = number(String(body[Range(m.range(at: 2), in: body)!])) { out[String(body[Range(m.range(at: 1), in: body)!])] = v }
        }
        return out
    }

    private func assertSameNames(_ rustValues: [String: Int], swift: [(String, Int)], renames: [String: String] = [:],
                                 swiftOnly: Set<String> = [], what: String, file: StaticString = #filePath, line: UInt = #line) {
        var swiftByName: [String: Int] = [:]
        for (name, value) in swift { swiftByName[normalized(name)] = value }
        for (name, value) in rustValues {
            let key = normalized(renames[name] ?? name)
            guard let have = swiftByName[key] else { XCTFail("\(what): Rust \(name) = \(value) has no Swift counterpart", file: file, line: line); continue }
            XCTAssertEqual(have, value, "\(what): \(name)", file: file, line: line)
        }
        let rustKeys = Set(rustValues.keys.map { normalized(renames[$0] ?? $0) })
        for name in swiftByName.keys where !rustKeys.contains(name) && !swiftOnly.contains(name) {
            XCTFail("\(what): Swift \(name) is not in the firmware", file: file, line: line)
        }
    }

    func testCommandIDsMatchTheFirmware() throws {
        let consts = try rust("openpatch-proto/src/consts.rs")
        assertSameNames(try constants(inModule: "cmd", of: consts), swift: V1.CommandID.allCases.map { ("\($0)", Int($0.rawValue)) },
                        what: "command ids")
    }

    func testTLVTagsMatchTheFirmware() throws {
        let consts = try rust("openpatch-proto/src/consts.rs")
        assertSameNames(try constants(inModule: "tag", of: consts), swift: V1.Tag.allCases.map { ("\($0)", Int($0.rawValue)) },
                        what: "tags")
    }

    func testStateFlagsMatchTheFirmware() throws {
        let consts = try rust("openpatch-proto/src/consts.rs")
        let swift: [(String, V1.StateFlags)] = [
            ("SUSPENDED", .suspended), ("BOLUS_ACTIVE", .bolusActive), ("TEMP_ACTIVE", .tempActive), ("HAS_SCHEDULE", .basalProgrammed),
            ("LOW_RESERVOIR", .reservoirLow), ("ALARM", .alarm), ("FILLED", .filled), ("LOW_BATTERY", .batteryLow),
            ("WEAR_WARNING", .wearWarning), ("DOCKED", .docked), ("ACTIVE", .activePod), ("DRAWING", .drawing),
            ("PRIME_REQUIRED", .primeRequired), ("DIAG_ACTIVE", .diagActive), ("LATCHED", .latched),
        ]
        let rustFlags = try constants(inModule: "st", of: consts)
        XCTAssertEqual(Set(rustFlags.keys), Set(swift.map(\.0)), "every firmware flag is known to Swift and vice versa")
        for (name, flag) in swift { XCTAssertEqual(Int(flag.rawValue), rustFlags[name], name) }
    }

    func testResultCodesMatchTheFirmware() throws {
        let codes = try enumValues("Error", of: try rust("openpatch-proto/src/error.rs"))
        assertSameNames(codes, swift: V1.Result.allCases.map { ("\($0)", Int($0.rawValue)) }, swiftOnly: ["ok"], what: "result codes")
        // and every one of them is handled by the phone (no refusal falls through as "malformed")
        for result in V1.Result.allCases where result != .ok && result != .notFound {
            XCTAssertNotNil(V1Transport.nack(for: result, command: .getStatus), "\(result) falls through")
        }
    }

    func testHistoryEventKindsMatchTheFirmware() throws {
        let kinds = try enumValues("EventType", of: try rust("openpatch-core/src/log.rs"))
        assertSameNames(kinds, swift: V1.HistoryType.allCases.map { ("\($0)", Int($0.rawValue)) }, what: "history events")
    }

    func testFaultBitsMatchTheFirmware() throws {
        let source = try rust("openpatch-core/src/faults.rs")
        let regex = try NSRegularExpression(pattern: #"pub const ([A-Z_]+): Faults = Faults\(1 << (\d+)\);"#)
        var rustBits: [String: Int] = [:]
        for m in regex.matches(in: source, range: NSRange(source.startIndex..., in: source)) {
            rustBits[String(source[Range(m.range(at: 1), in: source)!])] = 1 << Int(source[Range(m.range(at: 2), in: source)!])!
        }
        let swift: [(String, Int)] = [("OCCLUSION", Int(V1.FaultBit.occlusion)), ("ENCODER_DEVIATION", Int(V1.FaultBit.encoderDeviation)),
                                      ("RESERVOIR_EMPTY", Int(V1.FaultBit.reservoirEmpty)), ("BATTERY_CRITICAL", Int(V1.FaultBit.batteryCritical)),
                                      ("LIMIT_EXCEEDED", Int(V1.FaultBit.limitExceeded)), ("INTERNAL", Int(V1.FaultBit.internalError)),
                                      ("NO_CALIBRATION", Int(V1.FaultBit.noCalibration)), ("WEAR_EXPIRED", Int(V1.FaultBit.wearExpired))]
        XCTAssertEqual(Set(rustBits.keys), Set(swift.map(\.0)))
        for (name, value) in swift { XCTAssertEqual(rustBits[name], value, name) }
    }

    func testFrameConstantsAndNotificationKindsMatchTheFirmware() throws {
        let consts = try rust("openpatch-proto/src/consts.rs")
        func top(_ name: String) throws -> Int {
            let regex = try NSRegularExpression(pattern: "pub const \(name): (?:u8|u16|usize) = ([^;]+);")
            let m = try XCTUnwrap(regex.firstMatch(in: consts, range: NSRange(consts.startIndex..., in: consts)), name)
            return try XCTUnwrap(number(String(consts[Range(m.range(at: 1), in: consts)!])), name)
        }
        XCTAssertEqual(try top("PROTO_VERSION"), Int(V1.version))
        XCTAssertEqual(try top("FRAME_HEADER"), V1.headerSize)
        XCTAssertEqual(try top("FRAME_CRC"), V1.crcSize)
        XCTAssertEqual(try top("FRAME_MAX"), V1.maxFrameSize)
        XCTAssertEqual(try top("FLAG_ENCRYPTED"), Int(V1.flagEncrypted))
        XCTAssertEqual(try top("FLAG_RESPONSE"), Int(V1.flagResponse))
        XCTAssertEqual(try top("RSP_BIT"), Int(V1.responseFlag))
        XCTAssertEqual(try top("SEQ_MAX"), 0xFFFE)
        XCTAssertEqual(try top("HIST_MAX_PER_RESPONSE"), V1.historyPageSize)
        XCTAssertEqual(try top("BASAL_SEGMENTS_MAX"), PumpConstants.maxBasalSegments)
        let notify = try constants(inModule: "notify", of: consts)
        XCTAssertEqual(notify["FRAME_TYPE"], Int(V1.notificationType))
        XCTAssertEqual(notify["DRAW_PROGRESS"], 1); XCTAssertEqual(notify["FAULT"], 2); XCTAssertEqual(notify["DRAW_DONE"], 3)
        XCTAssertEqual(notify["DRAW_STALLED"], 4); XCTAssertEqual(notify["DIAG_RAISED"], 5); XCTAssertEqual(notify["DIAG_CLEARED"], 6)
        XCTAssertEqual(notify["SELFTEST_PROGRESS"], 7)
        let draw = try constants(inModule: "draw", of: consts)
        XCTAssertEqual(draw["IDLE"], Int(FillState.idle.rawValue)); XCTAssertEqual(draw["DRAWING"], Int(FillState.drawing.rawValue))
        XCTAssertEqual(draw["DONE"], Int(FillState.done.rawValue)); XCTAssertEqual(draw["STALLED"], Int(FillState.stalled.rawValue))
        XCTAssertEqual(draw["ABORTED"], Int(FillState.aborted.rawValue))
    }

    // MARK: Drive presets

    private struct RustPreset { let id: Int; let stepsPerRev: Int; let ratio: Int; let num: Int; let den: Int; let name: String }

    private func rustPresets() throws -> [RustPreset] {
        let source = try rust("openpatch-core/src/drive_cal.rs")
        let ids = try enumValues("DriveId", of: source)
        let regex = try NSRegularExpression(pattern: #"Preset \{ id: DriveId::(\w+), steps_per_rev: (\d+), gear_ratio_x100: (\d+), uu_num: ([\d_]+), uu_den: ([\d_]+), bore_area_x100: \d+ \}"#)
        func group(_ m: NSTextCheckingResult, _ i: Int) -> String { String(source[Range(m.range(at: i), in: source)!]) }
        return regex.matches(in: source, range: NSRange(source.startIndex..., in: source)).compactMap { m in
            let name = group(m, 1)
            guard let id = ids[name], !name.hasPrefix("Test") else { return nil }    // host-test calibrations never ship
            return RustPreset(id: id, stepsPerRev: Int(group(m, 2))!, ratio: Int(group(m, 3))!, num: Int(group(m, 4).replacingOccurrences(of: "_", with: ""))!,
                              den: Int(group(m, 5).replacingOccurrences(of: "_", with: ""))!, name: name)
        }
    }

    func testAcceptedDrivesAreExactlyTheFirmwarePresetsTheyClaimToBe() throws {
        let presets = try rustPresets()
        XCTAssertGreaterThanOrEqual(presets.count, 8, "the parser found the firmware's presets")
        for accepted in DriveCalibration.firmwarePresets {
            let preset = try XCTUnwrap(presets.first { $0.id == Int(accepted.driveID) }, "firmware has no preset \(accepted.driveID)")
            XCTAssertEqual(Int(accepted.microUnitsPerStep), preset.num / preset.den, "\(preset.name): floor of uU per step as the pod reports it")
            XCTAssertEqual(Int(accepted.stepsPerRevolution), preset.stepsPerRev, preset.name)
            XCTAssertEqual(Int(accepted.gearRatioTimes100), preset.ratio, preset.name)
        }
    }

    func testEveryOtherFirmwarePresetIsRefusedOnPurpose() throws {
        let accepted = Set(DriveCalibration.firmwarePresets.map { Int($0.driveID) })
        for preset in try rustPresets() where !accepted.contains(preset.id) {
            let reported = DriveCalibration(driveID: UInt16(preset.id), microUnitsPerStep: UInt32(preset.num / preset.den),
                                            stepsPerRevolution: UInt16(preset.stepsPerRev), gearRatioTimes100: UInt16(preset.ratio))
            XCTAssertFalse(reported.isKnown, "\(preset.name) must be refused")
            XCTAssertNotNil(DriveCalibration.refusedFirmwarePresetIDs[UInt16(preset.id)], "\(preset.name): refusal needs a reason on record")
            XCTAssertEqual(CalibrationProblem.check(reported), .unknown(driveID: UInt16(preset.id), microUnitsPerStep: UInt32(preset.num / preset.den)))
        }
    }

    func testOnlyTheCupPodForbidsSuctionDrawExactlyLikeTheFirmware() throws {
        let source = try rust("openpatch-core/src/drive_cal.rs")
        let ids = try enumValues("DriveId", of: source)
        let regex = try NSRegularExpression(pattern: #"allows_draw\(&self\) -> bool \{\s*!matches!\(self\.id, ([^)]+)\)"#)
        let m = try XCTUnwrap(regex.firstMatch(in: source, range: NSRange(source.startIndex..., in: source)))
        let list = String(source[Range(m.range(at: 1), in: source)!])
        let forbidden = Set(list.components(separatedBy: "|").map { $0.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: "DriveId::", with: "") }.compactMap { ids[$0] })
        XCTAssertEqual(forbidden, [0x26, 0x27], "both cup bores have no check valve")
        for drive in DriveCalibration.firmwarePresets {
            XCTAssertEqual(drive.allowsSuctionDraw, !forbidden.contains(Int(drive.driveID)), drive.presetName ?? "")
        }
    }

    func testAssistedFillRateMatchesTheFirmware() throws {
        let limits = try rust("openpatch-core/src/limits.rs")
        let regex = try NSRegularExpression(pattern: #"pub const ASSISTED_FILL_PPS: u32 = (\d+);"#)
        let m = try XCTUnwrap(regex.firstMatch(in: limits, range: NSRange(limits.startIndex..., in: limits)))
        XCTAssertEqual(Int(limits[Range(m.range(at: 1), in: limits)!]), PumpConstants.assistedFillStepsPerSecond)
    }
}
