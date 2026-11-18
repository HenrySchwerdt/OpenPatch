import XCTest
@testable import OpenPatchCore

/// Minimal firmware stand-in: answers wire v1 frames the way the spec describes, records every request.
private final class FakeFirmwareLink: FrameLink {
    var isConnected = true
    var requests: [V1.Message] = []
    var resultFor: [UInt8: V1.Result] = [:]
    var corruptSeq = false
    var ignoreFromID = false

    var flags: UInt16 = V1.StateFlags.suspended.rawValue | V1.StateFlags.filled.rawValue
    var faultMask: UInt16 = 0
    var reservoirMU: UInt32 = 100_000
    var batteryMV: UInt16 = 3_750
    var bolusRemainingMU: UInt32 = 0
    var tempRate: UInt16 = 0
    var tempRemaining: UInt16 = 0
    var nextEventID: UInt32 = 1
    var history: [V1.HistoryEvent] = []

    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { isConnected = true; completion(.success(())) }
    func disconnect() { isConnected = false }

    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        let request = try! V1.decode(frame)
        requests.append(request)
        var tlvs = [V1.TLV(.result, u8: (resultFor[request.type] ?? .ok).rawValue)]
        switch request.type {
        case V1.CommandID.getStatus.rawValue:
            tlvs += [V1.TLV(.stateFlags, u16: flags), V1.TLV(.reservoirMU, u32: reservoirMU), V1.TLV(.batteryMV, u16: batteryMV),
                     V1.TLV(.bolusRemainingMU, u32: bolusRemainingMU), V1.TLV(.tempRateMUh, u16: tempRate),
                     V1.TLV(.tempRemainingMin, u16: tempRemaining), V1.TLV(.deliveredMU, u32: 5_000),
                     V1.TLV(.faultMask, u16: faultMask), V1.TLV(.nextEventID, u32: nextEventID)]
        case V1.CommandID.getHistory.rawValue:
            var from: UInt32 = 0
            if let v = request.u32(.fromID), !ignoreFromID { from = v }
            tlvs += history.filter { $0.id >= from }.prefix(10).map { V1.TLV(tag: V1.Tag.historyEvent.rawValue, value: $0.bytes) }
            tlvs.append(V1.TLV(.nextEventID, u32: nextEventID))
        default: break
        }
        let reply = V1.Message(type: request.type | V1.responseFlag, flags: V1.flagResponse, seq: corruptSeq ? seq &+ 1 : seq, tlvs: tlvs)
        completion(.success(V1.encode(reply)))
    }

    func requests(of id: V1.CommandID) -> [V1.Message] { requests.filter { $0.type == id.rawValue } }
}

final class V1TransportTests: XCTestCase {
    private var link: FakeFirmwareLink!
    private var events: [PodEvent] = []
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private var checkpoints: [V1Transport.Checkpoint] = []

    private func makeTransport(phase: PodPhase = .unpaired, initialSequence: UInt16 = 1, cursor: UInt32? = nil,
                               keepLink: Bool = false) -> V1Transport {
        if !keepLink { link = FakeFirmwareLink() }
        events = []
        let transport = V1Transport(link: link, initialPhase: phase, initialSequence: initialSequence, initialHistoryCursor: cursor,
                                    clock: { [now] in now }, timeOfDayMilliseconds: { 43_200_000 })
        transport.checkpointHandler = { [unowned self] in checkpoints.append($0) }
        transport.eventHandler = { [unowned self] in events.append($0) }
        return transport
    }

    private func send(_ transport: V1Transport, _ command: Command) -> Result<Response, TransportError> {
        var result: Result<Response, TransportError>!
        transport.send(command) { result = $0 }
        return result
    }

    private func status(_ result: Result<Response, TransportError>, file: StaticString = #filePath, line: UInt = #line) -> PodStatus? {
        guard case .success(.ok(let status)) = result else { XCTFail("\(result)", file: file, line: line); return nil }
        return status
    }

    // MARK: mapping of commands to wire

    func test_bolus_sendsAmountInMilliUnitsAndTimeOfDay_thenReadsStatus() throws {
        let transport = makeTransport(phase: .active)
        link.flags = 0
        link.bolusRemainingMU = 1_500
        link.flags = V1.StateFlags.bolusActive.rawValue
        let result = send(transport, .bolus(id: 77, pulses: 40))   // 2.0 U
        let bolus = try XCTUnwrap(link.requests(of: .bolus).first)
        XCTAssertEqual(bolus.u32(.amountMU), 2000)
        XCTAssertEqual(bolus.u32(.timeOfDayMS), 43_200_000)
        XCTAssertEqual(link.requests.map(\.type), [V1.CommandID.bolus.rawValue, V1.CommandID.getStatus.rawValue])
        let podStatus = try XCTUnwrap(status(result))
        XCTAssertEqual(podStatus.bolus, BolusStatus(id: 77, requestedPulses: 40, deliveredPulses: 10))
    }

    func test_tempBasal_usesMilliUnitsPerHour_andRoundsDurationUpToThirtyMinutes() throws {
        let transport = makeTransport(phase: .active)
        link.flags = V1.StateFlags.tempActive.rawValue
        link.tempRate = 2000; link.tempRemaining = 60
        _ = send(transport, .setTempBasal(rateTicks: 40, durationMinutes: 31))   // 2.0 U/h for 31 min -> 60 min on the wire
        let request = try XCTUnwrap(link.requests(of: .setTempBasal).first)
        XCTAssertEqual(request.u16(.rateMUh), 2000)
        XCTAssertEqual(request.u16(.durationMin), 60)
        let result = send(transport, .setTempBasal(rateTicks: 0, durationMinutes: 1))
        XCTAssertEqual(link.requests(of: .setTempBasal).last?.u16(.durationMin), 30)
        XCTAssertEqual(status(result)?.tempBasal, TempBasalStatus(rateTicks: 40, remainingMinutes: 60))
    }

    func test_basalProgram_becomesBasalSegTLVs() throws {
        let transport = makeTransport(phase: .primed)
        let program = try BasalProgram(segments: [BasalSegment(startOffset: 0, unitsPerHour: 0.8), BasalSegment(startOffset: 6 * 3600, unitsPerHour: 1.25)])
        _ = send(transport, .setBasalProgram(program))
        let request = try XCTUnwrap(link.requests(of: .setBasalSchedule).first)
        let segments = request.tlvs.filter { $0.tag == V1.Tag.basalSeg.rawValue }.map(\.value)
        XCTAssertEqual(segments, [[0, 0x20, 0x03], [12, 0xE2, 0x04]])   // slot 0: 800 mU/h, slot 12: 1250 mU/h (LE)
    }

    func test_basalProgramWithMoreThan24Segments_isRejectedLocally() throws {
        let transport = makeTransport(phase: .primed)
        let segments = (0..<30).map { BasalSegment(startOffset: Double($0) * 1800, unitsPerHour: $0 % 2 == 0 ? 1.0 : 1.5) }
        let program = try BasalProgram(segments: segments)
        XCTAssertEqual(send(transport, .setBasalProgram(program)), .success(.rejected(.limitExceeded)))
        XCTAssertTrue(link.requests.isEmpty)
    }

    func test_setLimits_isLocalOnly() {
        let transport = makeTransport(phase: .primed)
        _ = send(transport, .setLimits(SafetyLimits(maxBolus: 8, maxBasalRate: 3)))
        XCTAssertEqual(link.requests.map(\.type), [V1.CommandID.getStatus.rawValue], "only a status read, no wire command for limits")
    }

    // MARK: lifecycle hints

    func test_setupFlow_phaseHintsFollowTheWireCommands() {
        let transport = makeTransport()
        XCTAssertEqual(status(send(transport, .hello(protocolVersion: 1, time: now, utcOffsetMinutes: 0)))?.phase, .paired)

        XCTAssertEqual(status(send(transport, .confirmFill(pulses: 2000)))?.phase, .filled)
        let fill = link.requests(of: .fillPrime).last
        XCTAssertEqual(fill?.u8(.subOp), 1)
        XCTAssertEqual(fill?.u32(.fillMU), 100_000)

        XCTAssertEqual(status(send(transport, .prime))?.phase, .primed)
        let prime = link.requests(of: .fillPrime).last
        XCTAssertEqual(prime?.u8(.subOp), 2)
        XCTAssertEqual(prime?.u16(.primeSteps), 38)
        XCTAssertEqual(events, [.primeCompleted])

        link.flags = V1.StateFlags.filled.rawValue   // resumed: no suspended bit
        XCTAssertEqual(status(send(transport, .confirmAttached))?.phase, .active)
        XCTAssertEqual(link.requests(of: .resume).count, 1)
    }

    func test_suspendedFlagMapsToSuspendedPhase_andBack() {
        let transport = makeTransport(phase: .active)
        link.flags = V1.StateFlags.suspended.rawValue
        XCTAssertEqual(status(send(transport, .getStatus))?.phase, .suspended)
        link.flags = 0
        XCTAssertEqual(status(send(transport, .getStatus))?.phase, .active)
    }

    func test_deactivateSuspendsPodAndMarksDeactivated_helloStartsRefill() {
        let transport = makeTransport(phase: .active)
        link.flags = V1.StateFlags.suspended.rawValue
        XCTAssertEqual(status(send(transport, .deactivate))?.phase, .deactivated)
        XCTAssertEqual(link.requests(of: .suspend).count, 1)
        XCTAssertEqual(status(send(transport, .hello(protocolVersion: 1, time: now, utcOffsetMinutes: 0)))?.phase, .paired)
    }

    // MARK: status parsing

    func test_statusParsing_reservoirBatteryFault() {
        let transport = makeTransport(phase: .active)
        link.flags = V1.StateFlags.alarm.rawValue
        link.faultMask = V1.FaultBit.occlusion
        link.reservoirMU = 42_190
        link.batteryMV = 3_750
        let podStatus = status(send(transport, .getStatus))
        XCTAssertEqual(podStatus?.phase, .faulted)
        XCTAssertEqual(podStatus?.faultCode, .occlusion)
        XCTAssertEqual(podStatus?.reservoirPulses, 843)           // 42.19 U -> 843 pulses of 0.05 U
        XCTAssertEqual(podStatus?.batteryPercent, 50)
        XCTAssertEqual(podStatus?.podTime, now)
    }

    func test_acknowledgedFaultDoesNotResumeDelivery() {
        let transport = makeTransport(phase: .active)
        link.faultMask = V1.FaultBit.reservoirEmpty
        XCTAssertEqual(status(send(transport, .getStatus))?.phase, .faulted)
        link.faultMask = 0
        link.flags = V1.StateFlags.suspended.rawValue
        XCTAssertEqual(status(send(transport, .silenceAlarm))?.phase, .suspended)
        XCTAssertEqual(link.requests(of: .acknowledge).count, 1)
    }

    // MARK: result codes

    func test_resultCodesMapToNackReasons() {
        let cases: [(V1.Result, NackReason)] = [(.busy, .busy), (.hourly, .hourlyLimit), (.limit, .limitExceeded),
                                                (.badArg, .malformed), (.reservoir, .insufficientReservoir),
                                                (.suspended, .invalidState), (.fault, .invalidState), (.replay, .session)]
        for (code, reason) in cases {
            let transport = makeTransport(phase: .active)
            link.resultFor[V1.CommandID.bolus.rawValue] = code
            XCTAssertEqual(send(transport, .bolus(id: 1, pulses: 20)), .success(.rejected(reason)), "\(code)")
            XCTAssertEqual(link.requests.count, 1, "no status read after a rejected command")
        }
    }

    func test_cancelWithNothingToCancel_isTreatedAsSuccess() {
        let transport = makeTransport(phase: .active)
        link.flags = 0
        link.resultFor[V1.CommandID.cancelBolus.rawValue] = .notFound
        link.resultFor[V1.CommandID.cancelTempBasal.rawValue] = .notFound
        XCTAssertNotNil(status(send(transport, .cancelBolus)))
        XCTAssertNotNil(status(send(transport, .cancelTempBasal)))
    }

    // MARK: history -> events

    func test_historyIsPolledAfterStatus_withoutReplayingOldEventsOnFirstConnect() {
        let transport = makeTransport(phase: .active)
        link.flags = 0
        link.nextEventID = 50
        link.history = [V1.HistoryEvent(id: 49, timeSeconds: 1, type: V1.HistoryType.lowReservoir.rawValue, a: 9_000, b: 0)]
        _ = send(transport, .getStatus)
        XCTAssertTrue(events.isEmpty, "first status only positions the cursor")
        XCTAssertTrue(link.requests(of: .getHistory).isEmpty)

        _ = send(transport, .bolus(id: 5, pulses: 40))
        link.nextEventID = 54
        link.history = [
            V1.HistoryEvent(id: 50, timeSeconds: 10, type: V1.HistoryType.bolusCancel.rawValue, a: 1_000, b: 0),   // 1 U undelivered
            V1.HistoryEvent(id: 51, timeSeconds: 11, type: V1.HistoryType.tempCommFallback.rawValue, a: 0, b: 0),
            V1.HistoryEvent(id: 52, timeSeconds: 12, type: V1.HistoryType.lowReservoir.rawValue, a: 9_000, b: 0),
            V1.HistoryEvent(id: 53, timeSeconds: 13, type: V1.HistoryType.fault.rawValue, a: Int32(V1.FaultBit.occlusion), b: 0)
        ]
        _ = send(transport, .getStatus)
        XCTAssertEqual(events, [.bolusCompleted(id: 5, deliveredPulses: 20), .tempBasalRevertedCommLoss,
                                .lowReservoir(pulses: 180), .fault(.occlusion)])
        XCTAssertEqual(link.requests(of: .getHistory).last?.u32(.fromID), 50)

        events = []
        _ = send(transport, .getStatus)
        XCTAssertTrue(events.isEmpty, "cursor advanced, nothing replayed")
    }

    func test_bolusDoneEvent_reportsFullAmount() {
        let transport = makeTransport(phase: .active)
        link.flags = 0
        link.nextEventID = 10
        _ = send(transport, .getStatus)
        _ = send(transport, .bolus(id: 9, pulses: 30))
        link.nextEventID = 12
        link.history = [V1.HistoryEvent(id: 10, timeSeconds: 0, type: V1.HistoryType.bolusStart.rawValue, a: 1500, b: 0),
                        V1.HistoryEvent(id: 11, timeSeconds: 0, type: V1.HistoryType.bolusDone.rawValue, a: 0, b: 0)]
        _ = send(transport, .getStatus)
        XCTAssertEqual(events, [.bolusCompleted(id: 9, deliveredPulses: 30)])
    }

    // MARK: sequence numbers & errors

    func test_sequenceNumbersStrictlyIncrease_andRespectInitialSequence() {
        let transport = makeTransport(phase: .active, initialSequence: 500)
        _ = send(transport, .getStatus)
        _ = send(transport, .getStatus)
        XCTAssertEqual(link.requests.map(\.seq), [500, 501])
    }

    func test_sequenceNeverReaches0xFFFF() {
        let transport = makeTransport(phase: .active, initialSequence: 0xFFFD)
        for _ in 0..<4 { _ = send(transport, .getStatus) }
        XCTAssertTrue(link.requests.allSatisfy { $0.seq <= 0xFFFE })
    }

    func test_responseWithWrongSeq_isMalformed() {
        let transport = makeTransport(phase: .active)
        link.corruptSeq = true
        XCTAssertEqual(send(transport, .getStatus), .failure(.malformedResponse))
    }

    func test_sendWhileDisconnected_failsFast() {
        let transport = makeTransport(phase: .active)
        link.isConnected = false
        XCTAssertEqual(send(transport, .getStatus), .failure(.notConnected))
        XCTAssertTrue(link.requests.isEmpty)
    }

    // MARK: persistence across app restarts

    func test_checkpoint_reportsNextSequenceBeforeEachExchange() {
        checkpoints = []
        let transport = makeTransport(phase: .active, initialSequence: 40)
        _ = send(transport, .getStatus)
        _ = send(transport, .getStatus)
        XCTAssertEqual(Array(Set(checkpoints.map(\.nextSequence))).sorted(), [41, 42])
        XCTAssertEqual(link.requests.map(\.seq), [40, 41])
    }

    func test_restart_continuesSequenceAboveThePreviousSession() {
        checkpoints = []
        let first = makeTransport(phase: .active, initialSequence: 10)
        _ = send(first, .getStatus); _ = send(first, .getStatus)
        let saved = checkpoints.last!
        let second = makeTransport(phase: .active, initialSequence: saved.nextSequence, keepLink: true)
        _ = send(second, .getStatus)
        let seqs = link.requests.map(\.seq)
        XCTAssertEqual(seqs, [10, 11, 12])
        XCTAssertEqual(seqs, seqs.sorted())
        XCTAssertEqual(Set(seqs).count, seqs.count)
    }

    func test_cursor_isCheckpointedOnFirstStatusAndAfterEvents() {
        checkpoints = []
        let transport = makeTransport(phase: .active)
        link.flags = 0; link.nextEventID = 50
        _ = send(transport, .getStatus)
        XCTAssertEqual(checkpoints.last?.historyCursor, 50)
        link.nextEventID = 52
        link.history = [V1.HistoryEvent(id: 50, timeSeconds: 0, type: V1.HistoryType.tempDone.rawValue, a: 0, b: 0),
                        V1.HistoryEvent(id: 51, timeSeconds: 0, type: V1.HistoryType.lowReservoir.rawValue, a: 9000, b: 0)]
        _ = send(transport, .getStatus)
        XCTAssertEqual(checkpoints.last?.historyCursor, 52)
    }

    func test_restart_withPersistedCursor_deliversMissedEventsExactlyOnce() {
        let first = makeTransport(phase: .active)
        link.flags = 0; link.nextEventID = 50
        _ = send(first, .getStatus)
        let cursorBeforeCrash = checkpoints.last!.historyCursor

        // events happen while the app is not running
        link.nextEventID = 53
        link.history = [V1.HistoryEvent(id: 50, timeSeconds: 0, type: V1.HistoryType.tempDone.rawValue, a: 0, b: 0),
                        V1.HistoryEvent(id: 51, timeSeconds: 0, type: V1.HistoryType.lowReservoir.rawValue, a: 9000, b: 0),
                        V1.HistoryEvent(id: 52, timeSeconds: 0, type: V1.HistoryType.fault.rawValue, a: Int32(V1.FaultBit.occlusion), b: 0)]
        let second = makeTransport(phase: .active, cursor: cursorBeforeCrash, keepLink: true)
        _ = send(second, .getStatus)
        XCTAssertEqual(events, [.tempBasalEnded, .lowReservoir(pulses: 180), .fault(.occlusion)])

        // a second restart with the newly persisted cursor does not replay them
        let third = makeTransport(phase: .active, cursor: checkpoints.last!.historyCursor, keepLink: true)
        _ = send(third, .getStatus)
        XCTAssertTrue(events.isEmpty)
    }

    func test_eventsOlderThanTheCursor_areDroppedEvenIfPodReturnsThem() {
        let transport = makeTransport(phase: .active, cursor: 51)
        link.flags = 0; link.nextEventID = 53
        link.history = [V1.HistoryEvent(id: 50, timeSeconds: 0, type: V1.HistoryType.tempDone.rawValue, a: 0, b: 0),   // already handled
                        V1.HistoryEvent(id: 51, timeSeconds: 0, type: V1.HistoryType.lowReservoir.rawValue, a: 9000, b: 0),
                        V1.HistoryEvent(id: 52, timeSeconds: 0, type: V1.HistoryType.lowBattery.rawValue, a: 3400, b: 0)]
        // simulate a pod that ignores FROM_ID by returning everything
        link.ignoreFromID = true
        _ = send(transport, .getStatus)
        XCTAssertEqual(events.count, 2)
        XCTAssertFalse(events.contains(.tempBasalEnded))
    }
}
