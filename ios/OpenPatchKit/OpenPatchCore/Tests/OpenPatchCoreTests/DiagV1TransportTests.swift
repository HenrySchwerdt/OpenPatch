import XCTest
@testable import OpenPatchCore

/// A pod that speaks the diagnostics extension: status with DIAG_SUMMARY, paged fault log, self-test, ClearDiag.
private final class DiagFakeLink: FrameLink {
    var isConnected = true
    var requests: [V1.Message] = []
    var records: [DiagRecord] = []
    var latched: [DiagCode] = []
    var nextRecIDLow: UInt16 = 1
    var includeDiagInStatus = true
    var garbageDiagTags = false
    var resultFor: [UInt8: V1.Result] = [:]
    var diagCodeInRefusal: DiagCode?
    var uid: UInt64? = 0x0123_4567_89AB_CDEF

    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { isConnected = true; completion(.success(())) }
    func disconnect() { isConnected = false }

    var nextID: UInt32 { (records.last?.recID ?? 0) + 1 }

    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        let request = try! V1.decode(frame)
        requests.append(request)
        var tlvs = [V1.TLV(.result, u8: (resultFor[request.type] ?? .ok).rawValue)]
        switch request.type {
        case V1.CommandID.getStatus.rawValue:
            tlvs += [V1.TLV(.stateFlags, u16: V1.StateFlags.suspended.rawValue | V1.StateFlags.filled.rawValue | V1.StateFlags.diagActive.rawValue),
                     V1.TLV(.reservoirMU, u32: 100_000), V1.TLV(.batteryMV, u16: 3750), V1.TLV(.faultMask, u16: 0), V1.TLV(.nextEventID, u32: 1)]
            if includeDiagInStatus {
                let summary = DiagSummary(topCode: records.last?.code, nextRecIDLow: nextRecIDLow)
                tlvs.append(V1.TLV(tag: V1.Tag.diagSummary.rawValue, value: garbageDiagTags ? summary.bytes + [0] : summary.bytes))
                tlvs.append(V1.TLV(tag: V1.Tag.fruHealth.rawValue, value: garbageDiagTags ? [1, 2, 3] : [0x1C, 0, 0, 0, 0, 0, 0, 0]))
                if let uid {
                    var w = ByteWriter(); w.u32(UInt32(uid & 0xFFFF_FFFF)); w.u32(UInt32(uid >> 32))
                    tlvs.append(V1.TLV(tag: V1.Tag.podUID.rawValue, value: garbageDiagTags ? [9] : w.bytes))
                }
            }
        case V1.CommandID.getHistory.rawValue:
            tlvs.append(V1.TLV(.nextEventID, u32: 1))
        case V1.CommandID.getFaultLog.rawValue:
            let from = request.u32(.fromID) ?? 0
            let oldest = records.first?.recID ?? nextID
            tlvs += [V1.TLV(.nextDiagID, u32: nextID), V1.TLV(.oldestDiagID, u32: oldest)]
            if !latched.isEmpty {
                var w = ByteWriter(); latched.forEach { w.u32($0.raw) }
                tlvs.append(V1.TLV(tag: V1.Tag.diagLatched.rawValue, value: w.bytes))
            }
            tlvs += records.filter { $0.recID >= max(from, oldest) }.prefix(4).map { V1.TLV(tag: V1.Tag.diagRecord.rawValue, value: $0.bytes) }
        case V1.CommandID.runSelfTest.rawValue:
            tlvs.append(V1.TLV(tag: V1.Tag.selftestState.rawValue, value: [2, request.u8(.subOp) ?? 0, 3, 0, 4, 0]))
        case V1.CommandID.clearDiag.rawValue:
            tlvs.append(V1.TLV(tag: V1.Tag.diagSummary.rawValue, value: DiagSummary(nextRecIDLow: nextRecIDLow).bytes))
        default: break
        }
        if resultFor[request.type] != nil && resultFor[request.type] != .ok, let code = diagCodeInRefusal {
            tlvs.append(V1.TLV(.diagCode, u32: code.raw))
        }
        completion(.success(V1.encode(V1.Message(type: request.type | V1.responseFlag, flags: V1.flagResponse, seq: seq, tlvs: tlvs))))
    }

    func requests(of id: V1.CommandID) -> [V1.Message] { requests.filter { $0.type == id.rawValue } }
}

final class DiagV1TransportTests: XCTestCase {
    private var link: DiagFakeLink!
    private var events: [PodEvent] = []
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private func makeTransport() -> V1Transport {
        link = DiagFakeLink()
        events = []
        let t = V1Transport(link: link, initialPhase: .paired, clock: { [now] in now }, timeOfDayMilliseconds: { 43_200_000 })
        t.eventHandler = { [unowned self] in events.append($0) }
        return t
    }

    private func rec(_ id: UInt32, _ code: DiagCode, severity: DiagSeverity = .warning, flags: DiagRecord.Flags? = nil) -> DiagRecord {
        let e = DiagCatalogue.lookup(code)!
        return DiagRecord(recID: id, code: code, severityRaw: severity.rawValue, actionRaw: e.action.rawValue, fruRaw: e.fru.rawValue,
                          flags: flags ?? (severity >= .warning ? [.active, .root] : [.root]))
    }

    private func diagIDs() -> [UInt32] {
        events.compactMap { (e: PodEvent) -> UInt32? in if case .diag(let r) = e { return r.recID } else { return nil } }
    }

    private func status(_ t: V1Transport) -> PodStatus? {
        var result: Result<Response, TransportError>?
        t.send(.getStatus) { result = $0 }
        guard case .success(.ok(let s)) = result else { return nil }
        return s
    }

    // MARK: Status

    func testStatusCarriesSummaryHealthAndUid() throws {
        let t = makeTransport()
        link.records = [rec(1, .tmagNoAck, severity: .fault)]
        link.nextRecIDLow = 2
        let s = try XCTUnwrap(status(t))
        XCTAssertEqual(s.diag?.topCode, .tmagNoAck)
        XCTAssertEqual(s.diag?.nextRecIDLow, 2)
        XCTAssertEqual(s.fruHealth?.state(of: .ctrl), .failed)
        XCTAssertEqual(s.uid, PodUID(raw: 0x0123_4567_89AB_CDEF))
        XCTAssertNil(s.faultCode, "faultCode stays the legacy summary computed from FAULT_MASK")
    }

    func testAV1PodStatusHasNoDiagnosticsAndGarbageSizedTagsAreIgnored() throws {
        let t = makeTransport()
        link.includeDiagInStatus = false
        var s = try XCTUnwrap(status(t))
        XCTAssertEqual([s.diag == nil, s.fruHealth == nil, s.uid == nil], [true, true, true])
        link.includeDiagInStatus = true
        link.garbageDiagTags = true
        s = try XCTUnwrap(status(t), "wrong sized diagnostic tags never fail the status")
        XCTAssertEqual([s.diag == nil, s.fruHealth == nil, s.uid == nil], [true, true, true])
        XCTAssertEqual(s.reservoirPulses, 2000, "the legacy fields are unchanged")
        XCTAssertTrue(link.requests(of: .getFaultLog).isEmpty)
    }

    /// The old parser (the existing `parseStatus`) skips the new tags: the legacy projection is identical with and without them.
    func testLegacyFieldsAreIdenticalWithAndWithoutTheNewTags() throws {
        let t = makeTransport()
        link.includeDiagInStatus = false
        var legacy = try XCTUnwrap(status(t))
        link.includeDiagInStatus = true
        var extended = try XCTUnwrap(status(t))
        XCTAssertNotNil(extended.diag)
        legacy.diag = nil; extended.diag = nil
        legacy.fruHealth = nil; extended.fruHealth = nil
        legacy.uid = nil; extended.uid = nil
        XCTAssertEqual(legacy, extended)
    }

    func testHistoryEvent31OnlyTellsAV1ReaderThatSomethingHappened() {
        let t = makeTransport()
        XCTAssertNil(t.domainEvent(for: V1.HistoryEvent(id: 1, timeSeconds: 0, type: 31, a: Int32(bitPattern: DiagCode.vmotStuckOn.raw), b: 1840)))
    }

    // MARK: GetFaultLog

    func testFaultLogPagesUntilNextIDAndKeepsTheLatchedSet() throws {
        let t = makeTransport()
        link.records = (1...10).map { rec(UInt32($0), .batteryLow) }
        link.latched = [.vmotStuckOn, .latchCannotClear]
        var result: Result<FaultLog, DiagCommandError>?
        t.getFaultLog(from: 0) { result = $0 }
        let log = try XCTUnwrap(try? result?.get())
        XCTAssertEqual(log.records.map(\.recID), Array(1...10).map(UInt32.init))
        XCTAssertEqual(log.latched, [.vmotStuckOn, .latchCannotClear])
        XCTAssertEqual([log.nextID, log.oldestID], [11, 1])
        XCTAssertEqual(link.requests(of: .getFaultLog).count, 3, "4 records per frame")
        XCTAssertEqual(link.requests(of: .getFaultLog).map { $0.u32(.fromID) }, [0, 5, 9])
        XCTAssertEqual(link.requests(of: .getFaultLog).first?.u8(.maxEvents), 4)

        // from the middle
        link.requests = []
        t.getFaultLog(from: 8) { result = $0 }
        XCTAssertEqual((try? result?.get())?.records.map(\.recID), [8, 9, 10])
    }

    func testEmptyLog() throws {
        let t = makeTransport()
        var result: Result<FaultLog, DiagCommandError>?
        t.getFaultLog(from: 0) { result = $0 }
        XCTAssertEqual(try result?.get(), FaultLog(records: [], latched: [], nextID: 1, oldestID: 1))
    }

    // MARK: Commands and refusals

    func testRefusalsCarryTheReasonAndTheCodeThePodNamed() {
        let t = makeTransport()
        link.resultFor[V1.CommandID.runSelfTest.rawValue] = .selfTestRefused
        var test: Result<SelfTestState, DiagCommandError>?
        t.runSelfTest(.postA) { test = $0 }
        XCTAssertEqual(test, .failure(.nack(.selfTestRefused, code: nil)))

        link.resultFor[V1.CommandID.clearDiag.rawValue] = .notClearable
        link.diagCodeInRefusal = .vmotStuckOn
        var clear: Result<DiagSummary, DiagCommandError>?
        t.clearDiag(.vmotStuckOn) { clear = $0 }
        XCTAssertEqual(clear, .failure(.nack(.notClearable, code: .vmotStuckOn)))

        link.resultFor[V1.CommandID.clearDiag.rawValue] = .unsupported
        t.clearDiag(nil) { clear = $0 }
        XCTAssertEqual(clear, .failure(.nack(.unsupported, code: .vmotStuckOn)))
    }

    func testSelfTestAndClearSuccess() throws {
        let t = makeTransport()
        var test: Result<SelfTestState, DiagCommandError>?
        t.runSelfTest(.postS) { test = $0 }
        let state = try XCTUnwrap(try? test?.get())
        XCTAssertEqual(state.phase, .done)
        XCTAssertEqual(state.kind, .postS)
        XCTAssertEqual([state.stepsPassed, state.stepsFailed], [3, 4])
        XCTAssertEqual(link.requests(of: .runSelfTest).first?.u8(.subOp), 1)

        var clear: Result<DiagSummary, DiagCommandError>?
        t.clearDiag(nil) { clear = $0 }
        XCTAssertEqual(link.requests(of: .clearDiag).first?.diagCode, DiagCode.none, "nil clears every clearable W/F record: code 0")
        XCTAssertNotNil(try? clear?.get())
        t.clearDiag(.batteryLow) { clear = $0 }
        XCTAssertEqual(link.requests(of: .clearDiag).last?.diagCode, .batteryLow)
    }

    func testNotConnectedAndDefaultsOfTheProtocol() {
        let t = makeTransport()
        link.isConnected = false
        var result: Result<FaultLog, DiagCommandError>?
        t.getFaultLog(from: 0) { result = $0 }
        XCTAssertEqual(result, .failure(.transport(.notConnected)))
        // a transport that implements nothing answers "unsupported"
        final class Bare: OpenPatchTransport {
            var isConnected = true
            var eventHandler: ((PodEvent) -> Void)?
            func connect(completion: @escaping (Result<Void, TransportError>) -> Void) {}
            func disconnect() {}
            func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {}
        }
        var summary: Result<DiagSummary, DiagCommandError>?
        Bare().clearDiag(nil) { summary = $0 }
        XCTAssertEqual(summary, .failure(.nack(.unsupported, code: nil)))
    }

    // MARK: Pull path

    func testPullPathForwardsNewRecordsAsEvents() throws {
        let t = makeTransport()
        link.records = [rec(1, .boot, severity: .info), rec(2, .batteryLow), rec(3, .tmagNoAck, severity: .fault),
                        DiagRecord(recID: 4, code: .batteryLow, severityRaw: 1, actionRaw: 7, fruRaw: 11, flags: [.cleared, .root])]
        // an old record that is no longer active must not raise an alert on the first sync
        link.records[1].flags = [.root]
        link.nextRecIDLow = 5
        _ = status(t)
        XCTAssertEqual(diagIDs(), [3], "first sync: only still active W/F/L records")
        XCTAssertEqual(t.currentDiagCursor, 5)
        XCTAssertEqual(link.requests(of: .getFaultLog).count, 1)

        // nothing moved: no extra request
        events = []
        _ = status(t)
        XCTAssertEqual(link.requests(of: .getFaultLog).count, 1)
        XCTAssertTrue(events.isEmpty)

        // a new warning, a new info record and a clear record arrive
        link.records += [rec(5, .tempLow), rec(6, .boot, severity: .info),
                         DiagRecord(recID: 7, code: .tmagNoAck, severityRaw: 2, actionRaw: 9, fruRaw: 2, flags: [.cleared, .root])]
        link.nextRecIDLow = 8
        _ = status(t)
        XCTAssertEqual(events, [.diag(link.records[4]), .diagCleared(.tmagNoAck)], "W is raised, I is log only, a clear record is a retract")
        XCTAssertEqual(link.requests(of: .getFaultLog).last?.u32(.fromID), 5, "continues at the cursor")
        XCTAssertEqual(t.currentDiagCursor, 8)
    }

    func testPullPathCursorCanBeRestored() {
        let t = makeTransport()
        link.records = [rec(1, .tmagNoAck, severity: .fault), rec(2, .tempLow)]
        link.nextRecIDLow = 3
        t.restoreDiagCursor(2)
        _ = status(t)
        XCTAssertEqual(link.requests(of: .getFaultLog).first?.u32(.fromID), 2, "an app restart continues where it stopped")
        XCTAssertEqual(diagIDs(), [2])
    }

    // MARK: Notifications

    private func notification(kind: UInt8, arg: UInt32, record: DiagRecord? = nil) -> Data {
        var tlvs = [V1.TLV(tag: V1.Tag.notifyKind.rawValue, value: [kind]), V1.TLV(.notifyArg, u32: arg)]
        if let record { tlvs.append(V1.TLV(tag: V1.Tag.diagRecord.rawValue, value: record.bytes)) }
        return V1.encode(V1.Message(type: SecureChannel.notificationType, flags: V1.flagResponse, seq: 0, tlvs: tlvs))
    }

    func testNotificationFramesBecomeEvents() {
        let t = makeTransport()
        let record = rec(7, .vmotStuckOn, severity: .latched)
        t.handleNotification(notification(kind: 5, arg: record.code.raw, record: record))
        t.handleNotification(notification(kind: 6, arg: DiagCode.batteryLow.raw))
        t.handleNotification(notification(kind: 7, arg: (3 << 16) | 4))
        t.handleNotification(notification(kind: 2, arg: UInt32(V1.FaultBit.occlusion)))
        t.handleNotification(notification(kind: 5, arg: 1))              // raised without a record: dropped, the pull path catches up
        t.handleNotification(notification(kind: 99, arg: 0))             // unknown kind
        t.handleNotification(Data([1, 2, 3]))                            // garbage
        XCTAssertEqual(events, [.diag(record), .diagCleared(.batteryLow), .selfTest(passed: 3, failed: 4), .fault(.occlusion)])
    }

    func testNotificationAndGetFaultLogResponseHaveDifferentFrameTypes() throws {
        // GetFaultLog's response type is 0x20 | 0x80 = 0xA0; only notifications are type 0x90, so the type alone decides the nonce direction
        let keys = SessionHandshake.SessionKeys(keyC2P: [UInt8](repeating: 1, count: 16), keyP2C: [UInt8](repeating: 2, count: 16), salt: [9, 8, 7, 6])
        let channel = SecureChannel(keys: keys)
        let aes = SessionCrypto.AESCCM(key: keys.keyP2C)
        func seal(type: UInt8, dir: UInt8, seq: UInt16) -> Data {
            let payload: [UInt8] = [V1.Tag.result.rawValue, 1, 0]
            let body = payload.count + 8
            let header: [UInt8] = [1, type, V1.flagEncrypted | V1.flagResponse, UInt8(seq & 0xFF), UInt8(seq >> 8), UInt8(body), 0]
            let nonce = keys.salt + [dir, UInt8(seq & 0xFF), UInt8(seq >> 8)] + [UInt8](repeating: 0, count: 6)
            var bytes = header + aes.seal(nonce: nonce, aad: header, plaintext: payload)
            let crc = V1.crc16(bytes)
            bytes += [UInt8(crc & 0xFF), UInt8(crc >> 8)]
            return Data(bytes)
        }
        let response = seal(type: V1.CommandID.getFaultLog.rawValue | V1.responseFlag, dir: 1, seq: 5)
        let notification = seal(type: V1.notificationType, dir: 2, seq: 5)
        XCTAssertEqual(try channel.open(response).result, .ok)
        XCTAssertEqual(try channel.open(notification).result, .ok)
        XCTAssertEqual(try channel.open(response, as: .response).result, .ok)
        XCTAssertEqual(try channel.open(notification, as: .notification).result, .ok)
        XCTAssertThrowsError(try channel.open(notification, as: .response))
    }
}
