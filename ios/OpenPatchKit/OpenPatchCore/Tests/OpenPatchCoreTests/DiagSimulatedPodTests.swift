import XCTest
@testable import OpenPatchCore

/// `SimulatedPod.inject(code)`: every catalogue code driven end to end (docs/06-diagnostics.md 5.5, 6.1 "S").
final class DiagSimulatedPodTests: XCTestCase {
    private let start = Date(timeIntervalSince1970: 1_800_000_000)

    private func makePod() -> SimulatedPod {
        let pod = SimulatedPod(size: .u200, startDate: start)
        _ = pod.handle(.hello(protocolVersion: PumpConstants.protocolVersion, time: start, utcOffsetMinutes: 0))
        _ = pod.handle(.confirmFill(pulses: 2000))
        _ = pod.handle(.prime)
        pod.advance(by: Int(PumpConstants.primeDuration) + 1)
        _ = pod.drainEvents()
        return pod
    }

    func testEveryCatalogueCodeDrivesExactlyOneDiagEventAndTheRightLegacyFault() {
        for entry in DiagCatalogue.entries {
            let pod = makePod()
            let name = entry.code.description
            let record = pod.inject(entry.code, ctx: (a: 11, b: 22, c: 33))
            let events = pod.drainEvents()

            // the record is exactly what the catalogue says (and survives the wire)
            XCTAssertEqual(record.code, entry.code, name)
            XCTAssertEqual(record.severity, entry.severity, name)
            XCTAssertEqual(record.action, entry.action, name)
            XCTAssertEqual(record.fru, entry.fru, name)
            XCTAssertEqual(record.fru2, entry.fru2, name)
            XCTAssertEqual([record.ctxA, record.ctxB, Int32(record.ctxC)], [11, 22, 33], name)
            XCTAssertEqual(DiagRecord(bytes: record.bytes), record, name)
            XCTAssertEqual(record.isActive, entry.severity >= .warning, name)
            XCTAssertEqual(record.isLatched, entry.severity == .latched, name)

            let diagEvents = events.compactMap { event -> DiagRecord? in if case .diag(let r) = event { return r } else { return nil } }
            let faultEvents = events.compactMap { event -> FaultCode? in if case .fault(let f) = event { return f } else { return nil } }
            XCTAssertEqual(diagEvents.count, entry.severity >= .warning ? 1 : 0, "\(name): exactly one diag event (I is log only)")
            if entry.severity.stopsDelivery {
                let bit = try! XCTUnwrap(entry.legacyBit)
                XCTAssertEqual(faultEvents, [V1Transport.faultCode(mask: 1 << UInt16(bit))!], "\(name): the legacy fault is derived from the legacy bit")
                XCTAssertEqual(pod.phase, .faulted, name)
                XCTAssertNotNil(pod.status.faultCode, name)
            } else {
                XCTAssertTrue(faultEvents.isEmpty, name)
                XCTAssertNotEqual(pod.phase, .faulted, name)
            }

            let summary = pod.status.diag
            XCTAssertEqual(summary?.activeCount, entry.severity >= .warning ? 1 : 0, name)
            XCTAssertEqual(summary?.latchedCount, entry.severity == .latched ? 1 : 0, name)
            XCTAssertEqual(summary?.topCode, entry.severity >= .warning ? entry.code : nil, name)
        }
    }

    func testUnknownCodeBehavesLikeTheFirmwaresFallback() {
        let pod = makePod()
        let record = pod.inject(DiagCode(raw: 0x1FFF_FF00), ctx: (1, 2, 3))
        XCTAssertEqual(record.severity, .fault)
        XCTAssertEqual(record.fru, .fw)
        XCTAssertEqual(record.action, .reportBug)
        XCTAssertEqual(pod.phase, .faulted)
        XCTAssertEqual(pod.status.faultCode, .internalError)
    }

    func testCauseChainHeadlineIsTheRootAndHealthBlamesTheRootFRU() {
        let pod = makePod()
        let root = pod.inject(.ffcAbsent)
        let mid = pod.inject(.tmagNoAck, cause: root)
        let top = pod.inject(.angleChannelLost, cause: mid)
        XCTAssertEqual(top.causeRec, UInt16(truncatingIfNeeded: mid.recID))
        XCTAssertFalse(top.flags.contains(.root))
        XCTAssertTrue(root.flags.contains(.root))
        let status = pod.status
        XCTAssertEqual(status.diag?.topCode, .ffcAbsent, "the headline is the root cause")
        XCTAssertEqual(status.diag?.topFru, .ffc)
        XCTAssertEqual(status.fruHealth?.state(of: .ffc), .failed)
        XCTAssertEqual(status.fruHealth?.state(of: .podb), .unknown, "the consequences do not blame their own default FRU")
    }

    func testCoalescingAndEscalation() {
        let pod = makePod()
        let first = pod.inject(.tmagCrcErrors, ctx: (4, 3, 0))
        let again = pod.inject(.tmagCrcErrors, ctx: (5, 3, 0))
        XCTAssertEqual(again.recID, first.recID, "same code still active: coalesced")
        XCTAssertEqual(again.count, 2)
        XCTAssertEqual(again.ctxA, 5)
        XCTAssertEqual(pod.faultLog(from: 0).records.filter { $0.code == .tmagCrcErrors }.count, 1)
        XCTAssertNotEqual(pod.phase, .faulted)
        let escalated = pod.inject(.tmagCrcErrors, severity: .fault)
        XCTAssertNotEqual(escalated.recID, first.recID)
        XCTAssertTrue(escalated.flags.contains(.escalated))
        XCTAssertEqual(pod.phase, .faulted)
    }

    func testFruHealthNeverSaysOkWithoutAProof() {
        let pod = makePod()
        XCTAssertEqual(pod.status.fruHealth?.raw, 0)
        pod.markProven([.ctrl, .motor])
        XCTAssertEqual(pod.status.fruHealth?.state(of: .ctrl), .ok)
        pod.inject(.vmotStuckOn)
        XCTAssertEqual(pod.status.fruHealth?.state(of: .ctrl), .failed)
        XCTAssertEqual(pod.status.fruHealth?.state(of: .motor), .ok)
    }

    func testStatusOfAV1PodHasNoDiagnostics() {
        let pod = makePod()
        pod.reportsDiagnostics = false
        pod.inject(.batteryLow)
        XCTAssertNil(pod.status.diag)
        XCTAssertNil(pod.status.fruHealth)
        XCTAssertNil(pod.status.uid)
        let t = SimulatedTransport(pod: pod)
        t.connect { _ in }
        var result: Result<FaultLog, DiagCommandError>?
        t.getFaultLog(from: 0) { result = $0 }
        XCTAssertEqual(result, .failure(.nack(.unsupported, code: nil)))
    }

    // MARK: Through the transport

    func testTransportFaultLogClearAndSelfTest() throws {
        let pod = makePod()
        pod.uid = PodUID(raw: 0xABCD)
        let t = SimulatedTransport(pod: pod)
        var events: [PodEvent] = []
        t.eventHandler = { events.append($0) }
        t.connect { _ in }
        XCTAssertEqual(pod.status.uid, PodUID(raw: 0xABCD))

        let w = pod.inject(.batteryLow)
        let l = pod.inject(.vmotStuckOn)
        for i in 0..<9 { pod.inject(DiagCode(layer: 1, component: 0x06, fault: UInt16(100 + i))) }   // unknown codes: faults
        _ = pod.drainEvents()

        var log: FaultLog?
        t.getFaultLog(from: 0) { log = try? $0.get() }
        let fetched = try XCTUnwrap(log)
        XCTAssertEqual(fetched.records.count, 11, "all pages")
        XCTAssertEqual(fetched.records.map(\.recID), Array(1...11).map(UInt32.init))
        XCTAssertEqual(fetched.latched, [.vmotStuckOn])
        XCTAssertEqual(fetched.nextID, 12)
        var tail: FaultLog?
        t.getFaultLog(from: 10) { tail = try? $0.get() }
        XCTAssertEqual(tail?.records.map(\.recID), [10, 11])

        // ClearDiag: latched needs its verification test, the pod decides
        var cleared: Result<DiagSummary, DiagCommandError>?
        t.clearDiag(.vmotStuckOn) { cleared = $0 }
        XCTAssertEqual(cleared, .failure(.nack(.notClearable, code: .vmotStuckOn)))
        t.clearDiag(.tmagNoAck) { cleared = $0 }
        XCTAssertEqual(cleared, .failure(.nack(.invalidState, code: .tmagNoAck)), "not active")
        t.clearDiag(.batteryLow) { cleared = $0 }
        XCTAssertEqual((try cleared?.get())?.activeCount, 10)
        XCTAssertTrue(events.contains(.diagCleared(.batteryLow)))
        XCTAssertTrue(pod.faultLog(from: pod.faultLog(from: 0).nextID - 1).records.last?.isClearRecord == true, "the clear is part of the pull path")
        XCTAssertFalse(pod.faultLog(from: 0).records.first { $0.recID == w.recID }!.isActive)

        pod.markVerified(.vmotStuckOn)
        t.clearDiag(.vmotStuckOn) { cleared = $0 }
        XCTAssertNotNil(try? cleared?.get())
        XCTAssertEqual(pod.status.diag?.latchedCount, 0)
        _ = l
    }

    func testSelfTestOnlyWhileSuspended() {
        let pod = makePod()
        let t = SimulatedTransport(pod: pod)
        t.connect { _ in }
        var result: Result<SelfTestState, DiagCommandError>?
        t.runSelfTest(.postA) { result = $0 }
        XCTAssertEqual((try? result?.get())?.stepsFailed, 0)
        XCTAssertEqual(pod.status.diag?.postState, 2)
        _ = pod.handle(.setBasalProgram(try! BasalProgram.constant(unitsPerHour: 1.0)))
        _ = pod.handle(.confirmAttached)
        XCTAssertEqual(pod.phase, .active)
        t.runSelfTest(.postA) { result = $0 }
        XCTAssertEqual(result, .failure(.nack(.selfTestRefused, code: nil)))
    }
}
