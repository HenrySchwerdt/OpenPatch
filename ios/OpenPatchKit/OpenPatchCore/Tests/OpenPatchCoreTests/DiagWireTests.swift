import XCTest
@testable import OpenPatchCore

/// Decoding of the diagnostics protocol extension (docs/06-diagnostics.md 5.4): the shared golden frames written by the Rust suite
/// (`docs/vectors/diag-frames.json`), the record / summary models, and the tolerance of the decoders.
final class DiagWireTests: XCTestCase {
    // MARK: Helpers

    private func hex(_ s: String) -> [UInt8] {
        var out: [UInt8] = []
        var index = s.startIndex
        while index < s.endIndex {
            let next = s.index(index, offsetBy: 2)
            out.append(UInt8(s[index..<next], radix: 16)!)
            index = next
        }
        return out
    }

    private func loadVectors() throws -> [String: Any] {
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<6 { url.deleteLastPathComponent() }
        let data = try Data(contentsOf: url.appendingPathComponent("docs/vectors/diag-frames.json"))
        return try JSONSerialization.jsonObject(with: data) as! [String: Any]
    }

    /// The worked example of 5.4: `1-06-001` latched, 1840 mV against 1000 mV.
    private let exampleRecordBytes: [UInt8] = [
        0x05, 0, 0, 0, 0x00, 0x01, 0x60, 0x10, 0x03, 0x08, 0x01, 0x00, 0x2C, 0x01, 0, 0, 0x30, 0x07, 0, 0, 0xE8, 0x03, 0, 0, 0x39, 0x30, 0, 0, 0x01, 0x43, 0, 0,
    ]

    // MARK: Models

    func testWorkedExampleRecord() throws {
        let r = try XCTUnwrap(DiagRecord(bytes: exampleRecordBytes))
        XCTAssertEqual(r.recID, 5)
        XCTAssertEqual(r.code, .vmotStuckOn)
        XCTAssertEqual(r.severity, .latched)
        XCTAssertEqual(r.action, .replace)
        XCTAssertEqual(r.fru, .ctrl)
        XCTAssertNil(r.fru2)
        XCTAssertEqual([r.podSeconds, r.ctxC], [300, 12345])
        XCTAssertEqual([r.ctxA, r.ctxB], [1840, 1000])
        XCTAssertEqual(r.count, 1)
        XCTAssertEqual(r.flags, [.latched, .active, .root])
        XCTAssertTrue(r.isRoot && r.isActive && r.isLatched && !r.isClearRecord)
        XCTAssertEqual(r.bytes, exampleRecordBytes)
    }

    func testRecordDecoderIsTotalAndUnknownValuesAreFailSafe() throws {
        XCTAssertNil(DiagRecord(bytes: [UInt8](repeating: 0, count: 31)))
        XCTAssertNil(DiagRecord(bytes: [UInt8](repeating: 0, count: 33)))
        var raw = [UInt8](repeating: 0, count: 32)
        raw[8] = 9; raw[9] = 200; raw[10] = 99
        let r = try XCTUnwrap(DiagRecord(bytes: raw))
        XCTAssertEqual(r.severity, .fault, "an unknown severity is a fault")
        XCTAssertNil(r.action)
        XCTAssertNil(r.fru)
        XCTAssertEqual(r.bytes, raw, "lossless")
        // every random 32 byte pattern decodes and round trips
        var generator = SystemRandomNumberGenerator()
        for _ in 0..<500 {
            let bytes = (0..<32).map { _ in UInt8.random(in: 0...255, using: &generator) }
            XCTAssertEqual(DiagRecord(bytes: bytes)?.bytes, bytes)
        }
    }

    func testSummaryExample() throws {
        // 5.4 example with the current catalogue schema (2): 27 0E | 00 01 60 10 | 03 08 01 01 01 03 | 06 00 | 02 00
        let bytes: [UInt8] = [0x00, 0x01, 0x60, 0x10, 0x03, 0x08, 0x01, 0x01, 0x01, 0x03, 0x06, 0x00, 0x02, 0x00]
        let s = try XCTUnwrap(DiagSummary(bytes: bytes))
        XCTAssertEqual(s.topCode, .vmotStuckOn)
        XCTAssertEqual([s.topSeverityRaw, s.topActionRaw, s.topFruRaw], [3, 8, 1])
        XCTAssertEqual([s.latchedCount, s.activeCount, s.postState], [1, 1, 3])
        XCTAssertEqual(s.nextRecIDLow, 6)
        XCTAssertEqual(s.schema, 2)
        XCTAssertFalse(s.schemaDiffers)
        var old = bytes; old[12] = 0x01
        XCTAssertTrue(try XCTUnwrap(DiagSummary(bytes: old)).schemaDiffers, "a pod on catalogue schema 1 must be flagged")
        XCTAssertEqual(s.bytes, bytes)
        XCTAssertNil(DiagSummary(bytes: bytes + [0]))
        XCTAssertNil(DiagSummary(bytes: [UInt8](repeating: 0, count: 14))?.topCode, "0 = no active record")
    }

    func testFruHealthDecode() {
        let h = FruHealth(raw: 0x1C)   // CTRL failed (3 << 2), PODB ok (1 << 4)
        XCTAssertEqual(h.state(of: .ctrl), .failed)
        XCTAssertEqual(h.state(of: .podb), .ok)
        XCTAssertEqual(h.state(of: .motor), .unknown, "not proven means unknown, never ok")
        XCTAssertEqual(h.states.count, Fru.allCases.count)
        XCTAssertEqual(FruHealth.pack([.ctrl: .failed, .podb: .ok]), h)
        XCTAssertEqual(FruHealth.pack([.mags: .degraded]).state(of: .mags), .degraded)
        XCTAssertEqual(PodUID(raw: 0x0123_4567_89AB_CDEF).description, "0123456789abcdef")
    }

    func testCauseChain() {
        func rec(_ id: UInt32, _ code: DiagCode, cause: UInt32 = 0) -> DiagRecord {
            DiagRecord(recID: id, code: code, severityRaw: 2, actionRaw: 0, fruRaw: 0, flags: cause == 0 ? [.root, .active] : [.active], causeRec: UInt16(cause))
        }
        let root = rec(10, .i2cErrorRate), mid = rec(11, .tmagNoAck, cause: 10), top = rec(12, .angleChannelLost, cause: 11)
        let all = [root, mid, top]
        XCTAssertEqual(DiagChain.root(of: top, in: all), root)
        XCTAssertEqual(DiagChain.chain(from: top, in: all).records.map(\.recID), [12, 11, 10])
        XCTAssertFalse(DiagChain.chain(from: top, in: all).missingCause)
        let partial = DiagChain.chain(from: top, in: [mid, top])
        XCTAssertEqual(partial.records.map(\.recID), [12, 11])
        XCTAssertTrue(partial.missingCause, "cause not in log")
        XCTAssertEqual(DiagChain.root(of: root, in: all), root)
        // a cycle or a very deep chain ends at the depth bound
        let loop = [rec(1, .tmagNoAck, cause: 2), rec(2, .tmagNoAck, cause: 1)]
        XCTAssertLessThanOrEqual(DiagChain.chain(from: loop[0], in: loop).records.count, DiagChain.maxDepth)
    }

    // MARK: Golden frames shared with the Rust suite

    func testGoldenFramesDecodeAndMatchTheRustEncoding() throws {
        let file = try loadVectors()
        let keys = file["keys"] as! [String: String]
        let sessionKeys = SessionHandshake.SessionKeys(keyC2P: hex(keys["c2p"]!), keyP2C: hex(keys["p2c"]!), salt: hex(keys["salt"]!))
        let channel = SecureChannel(keys: sessionKeys)
        let frames = file["frames"] as! [[String: Any]]
        XCTAssertGreaterThanOrEqual(frames.count, 15)

        for f in frames {
            let name = f["name"] as! String
            let direction = f["direction"] as! String
            let type = UInt8(f["frame_type"] as! Int), seq = UInt16(f["seq"] as! Int)
            let payload = hex(f["payload"] as! String)
            let plain = Data(hex(f["wire_plain"] as! String)), encrypted = Data(hex(f["wire_encrypted"] as! String))
            XCTAssertLessThanOrEqual(encrypted.count, V1.maxFrameSize, name)

            // plain form: CRC, header, payload
            let message = try V1.decode(plain)
            XCTAssertEqual(message.type, type, name)
            XCTAssertEqual(message.seq, seq, name)
            XCTAssertEqual(message.tlvs.flatMap { [$0.tag, UInt8($0.value.count)] + $0.value }, payload, name)

            // encrypted form
            let expect = f["expect"] as! [String: Any]
            if direction == "command" {
                // commands are built by the phone: Swift must produce the very same bytes, plain and encrypted
                XCTAssertEqual(V1.encode(message), plain, "\(name): Swift plain encoding differs from Rust")
                XCTAssertEqual(channel.seal(message), encrypted, "\(name): Swift AES-CCM sealing differs from Rust")
                switch expect["command"] as! String {
                case "GetFaultLog":
                    XCTAssertEqual(message.u32(.fromID), UInt32(expect["from_id"] as! Int), name)
                    XCTAssertEqual(message.u8(.maxEvents), UInt8(expect["max_events"] as! Int), name)
                case "RunSelfTest": XCTAssertEqual(message.u8(.subOp), UInt8(expect["sub_op"] as! Int), name)
                case "ClearDiag": XCTAssertEqual(message.diagCode?.raw, UInt32(expect["code"] as! Int), name)
                default: XCTFail(name)
                }
            } else {
                let opened: V1.Message
                do { opened = try channel.open(encrypted, as: direction == "notification" ? .notification : .response) } catch { XCTFail("\(name): \(error)"); continue }
                XCTAssertEqual(opened.tlvs, message.tlvs, "\(name): decrypted payload differs from the plain one")
                XCTAssertEqual(opened.type, type, name)
                try check(expect, of: opened, direction: direction, name: name)
                try check(expect, of: message, direction: direction, name: name)
            }
        }
    }

    private func check(_ expect: [String: Any], of m: V1.Message, direction: String, name: String) throws {
        func int(_ k: String) -> Int { expect[k] as! Int }
        func records(_ list: [[String: Any]]) -> [DiagRecord] {
            list.map { DiagRecord(bytes: hex($0["bytes"] as! String))! }
        }
        if direction == "notification" {
            XCTAssertEqual(m.u8(.notifyKind), UInt8(int("kind")), name)
            XCTAssertEqual(m.u32(.notifyArg), UInt32(int("arg")), name)
            if let rec = expect["record"] as? [String: Any] {
                XCTAssertEqual(m.diagRecords, records([rec]), name)
            } else {
                XCTAssertTrue(m.diagRecords.isEmpty, name)
            }
            return
        }
        XCTAssertEqual(m.result.map { Int($0.rawValue) }, int("result"), name)
        if let flags = expect["flags"] as? Int {
            XCTAssertEqual(m.u16(.stateFlags), UInt16(flags), name)
            XCTAssertEqual(m.u16(.faultMask), UInt16(int("fault_mask")), name)
            let st = V1.StateFlags(rawValue: UInt16(flags))
            XCTAssertTrue(st.contains(.diagActive) && st.contains(.latched), name)
        }
        if let summary = expect["diag_summary"] as? [String: Any] {
            let s = try XCTUnwrap(m.diagSummary, name)
            XCTAssertEqual(s.topCode?.raw ?? 0, UInt32(summary["top_code"] as! Int), name)
            XCTAssertEqual([s.topSeverityRaw, s.topActionRaw, s.topFruRaw, s.latchedCount, s.activeCount, s.postState].map(Int.init),
                           ["top_sev", "top_action", "top_fru", "n_latched", "n_active", "post_state"].map { summary[$0] as! Int }, name)
            XCTAssertEqual([Int(s.nextRecIDLow), Int(s.schema)], [summary["next_rec_id_lo"] as! Int, summary["schema"] as! Int], name)
        }
        if let health = expect["fru_health"] as? Int { XCTAssertEqual(m.fruHealth?.raw, UInt64(health), name) }
        if let uid = expect["pod_uid"] as? String { XCTAssertEqual(m.podUID?.description, uid, name) }
        if let code = expect["diag_code"] as? Int { XCTAssertEqual(m.diagCode?.raw, UInt32(code), name) }
        if let next = expect["next_id"] as? Int {
            XCTAssertEqual(m.u32(.nextDiagID), UInt32(next), name)
            XCTAssertEqual(m.u32(.oldestDiagID), UInt32(int("oldest_id")), name)
            XCTAssertEqual(m.latchedCodes.map { Int($0.raw) }, expect["latched"] as! [Int], name)
            XCTAssertEqual(m.diagRecords, records(expect["records"] as! [[String: Any]]), name)
        }
        if let t = expect["selftest"] as? [String: Int] {
            let s = try XCTUnwrap(m.selfTestState, name)
            XCTAssertEqual([Int(s.phaseRaw), Int(s.kindRaw), Int(s.stepsPassed), Int(s.stepsFailed)],
                           [t["state"]!, t["kind"]!, t["steps_passed"]!, t["steps_failed"]!], name)
        }
    }

    // MARK: Constants and tolerance

    func testWireConstants() {
        XCTAssertEqual([V1.CommandID.getFaultLog, .runSelfTest, .clearDiag].map(\.rawValue), [0x20, 0x21, 0x22])
        XCTAssertEqual([V1.Tag.diagSummary, .fruHealth, .diagRecord, .nextDiagID, .oldestDiagID, .diagLatched, .selftestState, .diagCode, .podUID].map(\.rawValue),
                       Array(0x27...0x2F))
        XCTAssertEqual([V1.Result.selfTestRefused, .latched, .notClearable, .noSchedule].map(\.rawValue), [28, 29, 30, 31])
        XCTAssertEqual(V1Transport.nack(for: .noSchedule, command: .resume), .noSchedule)
        XCTAssertEqual(V1.StateFlags.diagActive.rawValue, 1 << 13)
        XCTAssertEqual(V1.StateFlags.latched.rawValue, 1 << 14)
        XCTAssertEqual(V1.HistoryType.diag.rawValue, 31)
        XCTAssertEqual(V1Transport.nack(for: .selfTestRefused, command: .getStatus), .selfTestRefused)
        XCTAssertEqual(V1Transport.nack(for: .latched, command: .resume), .latched)
        XCTAssertEqual(V1Transport.nack(for: .notClearable, command: .getStatus), .notClearable)
    }

    /// A response frame carries `id | 0x80`: no response type may equal another frame type (the notification type 0x90 in particular).
    func testNoResponseTypeCollidesWithAnyOtherFrameType() {
        let ids: [UInt8] = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x20, 0x21, 0x22]
        XCTAssertEqual(ids.count, Set(ids).count)
        XCTAssertTrue(ids.allSatisfy { V1.CommandID(rawValue: $0) != nil })
        XCTAssertTrue(ids.allSatisfy { $0 & V1.responseFlag == 0 })
        let responses = ids.map { $0 | V1.responseFlag }
        XCTAssertEqual(responses.count, Set(responses).count)
        let others = Set(ids + V1.handshakeTypes + V1.handshakeTypes.map { $0 | V1.responseFlag })
        XCTAssertTrue(Set(responses).isDisjoint(with: others))
        XCTAssertFalse(responses.contains(V1.notificationType))
        XCTAssertFalse(others.contains(V1.notificationType))
        XCTAssertEqual(V1.notificationType, SecureChannel.notificationType)
    }

    func testTheCurrentCadDriveIsKnownAndMatchesTheFirmwarePreset() {
        let d = DriveCalibration.nfp608_26_45_g16_20
        XCTAssertTrue(d.isKnown)
        XCTAssertEqual(d.driveID, 0x25)
        // 0.35 mm x 74.6 mm^2 / 10 / (20 x 26.45 x 20/16) = 0.0039486 U per step
        XCTAssertEqual(d.unitsPerStep, 0.0039486, accuracy: 1e-6) // the pod reports the floor in uU
        XCTAssertEqual(d.micrometresPerStep, 0.5293, accuracy: 1e-4)
        XCTAssertNil(CalibrationProblem.check(d))
        // the older pairs are NOT accepted: 15:12 would dose +56 %, 18:18 +25 %
        XCTAssertTrue(DriveCalibration(driveID: 0x24, microUnitsPerStep: 6_169, stepsPerRevolution: 20, gearRatioTimes100: 2_116).isKnown == false)
    }

    func testWrongSizedDiagnosticTLVsAreSkippedNeverFatal() {
        let m = V1.Message(type: 0x81, flags: V1.flagResponse, seq: 1, tlvs: [
            V1.TLV(.result, u8: 0),
            V1.TLV(tag: V1.Tag.diagSummary.rawValue, value: [UInt8](repeating: 0, count: 15)),
            V1.TLV(tag: V1.Tag.fruHealth.rawValue, value: [UInt8](repeating: 0, count: 7)),
            V1.TLV(tag: V1.Tag.podUID.rawValue, value: [UInt8](repeating: 0, count: 9)),
            V1.TLV(tag: V1.Tag.diagRecord.rawValue, value: [UInt8](repeating: 0, count: 31)),
            V1.TLV(tag: V1.Tag.diagLatched.rawValue, value: [1, 2, 3]),
            V1.TLV(tag: V1.Tag.selftestState.rawValue, value: [1]),
            V1.TLV(tag: V1.Tag.diagCode.rawValue, value: [1]),
        ])
        XCTAssertNil(m.diagSummary)
        XCTAssertNil(m.fruHealth)
        XCTAssertNil(m.podUID)
        XCTAssertTrue(m.diagRecords.isEmpty)
        XCTAssertTrue(m.latchedCodes.isEmpty)
        XCTAssertNil(m.selfTestState)
        XCTAssertNil(m.diagCode)
        XCTAssertEqual(m.result, .ok)
    }

    func testDecodersNeverCrashOnGarbage() {
        var generator = SystemRandomNumberGenerator()
        for _ in 0..<2000 {
            let count = Int.random(in: 0...80, using: &generator)
            let tlvs = (0..<Int.random(in: 0...6, using: &generator)).map { _ in
                V1.TLV(tag: UInt8.random(in: 0x25...0x30, using: &generator),
                       value: (0..<Int.random(in: 0...70, using: &generator)).map { _ in UInt8.random(in: 0...255, using: &generator) })
            }
            let m = V1.Message(type: UInt8.random(in: 0...255, using: &generator), seq: 1, tlvs: tlvs)
            _ = (m.diagSummary, m.fruHealth, m.podUID, m.diagRecords, m.latchedCodes, m.selfTestState, m.diagCode, m.result)
            _ = DiagRecord(bytes: (0..<count).map { _ in UInt8.random(in: 0...255, using: &generator) })
            _ = DiagSummary(bytes: (0..<count).map { _ in UInt8.random(in: 0...255, using: &generator) })
        }
    }
}
