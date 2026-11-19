import XCTest
@testable import OpenPatchCore

final class V1AssistedFillTransportTests: XCTestCase {
    private var link: WirePodLink!
    private var events: [PodEvent] = []

    private func transport(phase: PodPhase = .paired, calibration: DriveCalibration? = .nfp608_26_45_cupMiter1_1) -> V1Transport {
        link = WirePodLink()
        link.calibration = calibration
        events = []
        let t = V1Transport(link: link, initialPhase: phase, timeOfDayMilliseconds: { 0 })
        t.eventHandler = { [unowned self] in events.append($0) }
        return t
    }

    private func send(_ t: V1Transport, _ command: Command) -> Result<Response, TransportError> {
        var result: Result<Response, TransportError>!
        t.send(command) { result = $0 }
        return result
    }

    private func status(_ r: Result<Response, TransportError>) -> PodStatus? {
        guard case .success(.ok(let s)) = r else { return nil }
        return s
    }

    func test_assistedFill_sendsTheAmountInMilliUnits_andTheStatusShowsTheJob() throws {
        let t = transport()
        _ = send(t, .getStatus)                                   // learns the drive
        link.drawState = 1; link.drawRequestedMU = 20_000; link.drawDoneMU = 1_400
        link.flags = V1.StateFlags.suspended.rawValue | V1.StateFlags.drawing.rawValue
        let s = try XCTUnwrap(status(send(t, .assistedFill(pulses: 400))))
        XCTAssertEqual(link.requests(of: .assistedFill).last?.u32(.fillMU), 20_000)
        XCTAssertEqual(s.fill, FillStatus(state: .drawing, requestedUnits: 20, drawnUnits: 1.4, primeRequired: false))
        XCTAssertEqual(s.phase, .paired, "still drawing: nothing is confirmed yet")
    }

    func test_whenTheJobEnds_thePodIsFilled_butAnOldResultNeverFillsARefilledPod() throws {
        let t = transport()
        _ = send(t, .getStatus)
        _ = send(t, .assistedFill(pulses: 400))
        link.drawState = 2; link.drawRequestedMU = 20_000; link.drawDoneMU = 19_994
        link.flags = V1.StateFlags.suspended.rawValue | V1.StateFlags.primeRequired.rawValue
        XCTAssertEqual(status(send(t, .getStatus))?.phase, .filled)

        // the pod is removed, woken again for a refill: it still reports the old DONE job, which is not a new fill
        _ = send(t, .deactivate)
        _ = send(t, .hello(protocolVersion: 1, time: Date(), utcOffsetMinutes: 0))
        XCTAssertEqual(status(send(t, .getStatus))?.phase, .paired, "the old job does not fill a pod that was not refilled")
    }

    func test_aCancelledFillThatDrewSomethingFillsThePod() throws {
        let t = transport()
        _ = send(t, .getStatus)
        _ = send(t, .assistedFill(pulses: 400))
        link.drawState = 4; link.drawRequestedMU = 20_000; link.drawDoneMU = 4_200
        let s = try XCTUnwrap(status(send(t, .cancelAssistedFill)))
        XCTAssertEqual(link.requests(of: .assistedFill).last?.u32(.fillMU), 0, "amount 0 = cancel")
        XCTAssertEqual(s.fill?.state, .aborted)
        XCTAssertEqual(s.phase, .filled)
    }

    func test_aPodWithAnUnknownOrMissingDriveIsNeverAskedToRetract() {
        for cal in [nil, DriveCalibration(driveID: 0x77, microUnitsPerStep: 7_030, stepsPerRevolution: 20, gearRatioTimes100: 2_645)] {
            let t = transport(calibration: cal)
            _ = send(t, .getStatus)
            XCTAssertEqual(send(t, .assistedFill(pulses: 100)), .success(.rejected(.calibration)))
            XCTAssertTrue(link.requests(of: .assistedFill).isEmpty, "nothing went out")
        }
        let legacy = transport(calibration: .zwbpd006006_5_1)
        _ = send(legacy, .getStatus)
        XCTAssertEqual(send(legacy, .assistedFill(pulses: 100)), .success(.rejected(.unsupported)))
    }

    func test_theRefusalsOfTheCupPodAreReportedAsTheyAre() {
        let t = transport()
        _ = send(t, .getStatus)
        link.resultFor[V1.CommandID.assistedFill.rawValue] = .docked
        XCTAssertEqual(send(t, .assistedFill(pulses: 100)), .success(.rejected(.podDocked)))
        link.resultFor[V1.CommandID.resume.rawValue] = .primeRequired
        XCTAssertEqual(send(t, .confirmAttached), .success(.rejected(.primeRequired)))
        link.resultFor[V1.CommandID.fillPrime.rawValue] = .hourly
        XCTAssertEqual(send(t, .prime), .success(.rejected(.hourlyLimit)), "the take-up retry condition")
    }

    func test_aLostBolusReplyStillMapsTheHistoryToTheRightBolus() throws {
        let t = transport(phase: .active)
        _ = send(t, .getStatus)
        link.history = [V1.HistoryEvent(id: 1, timeSeconds: 10, type: V1.HistoryType.boot.rawValue, a: 0, b: 0)]
        link.nextEventID = 2
        _ = send(t, .getStatus)                                   // sets the history cursor to 2
        link.dropNext = 1
        XCTAssertEqual(send(t, .bolus(id: 42, pulses: 1)), .failure(.timeout))   // the pod executed it, the reply is lost
        link.history += [V1.HistoryEvent(id: 2, timeSeconds: 20, type: V1.HistoryType.bolusStart.rawValue, a: 50, b: 0),
                         V1.HistoryEvent(id: 3, timeSeconds: 22, type: V1.HistoryType.bolusDone.rawValue, a: 0, b: 0)]
        link.nextEventID = 4
        _ = send(t, .getStatus)
        XCTAssertEqual(events, [.bolusStarted(pulses: 1), .bolusCompleted(id: 42, deliveredPulses: 1)])
    }

    func test_aRefusedBolusDoesNotLeaveItsIdBehind() {
        let t = transport(phase: .active)
        _ = send(t, .getStatus)
        _ = send(t, .bolus(id: 1, pulses: 40))                    // accepted
        link.resultFor[V1.CommandID.bolus.rawValue] = .busy
        XCTAssertEqual(send(t, .bolus(id: 2, pulses: 1)), .success(.rejected(.busy)))
        link.resultFor[V1.CommandID.bolus.rawValue] = nil
        link.history = [V1.HistoryEvent(id: 1, timeSeconds: 10, type: V1.HistoryType.bolusDone.rawValue, a: 0, b: 0)]
        link.nextEventID = 2
        _ = send(t, .getStatus)                                   // first poll only sets the cursor
        link.history += [V1.HistoryEvent(id: 2, timeSeconds: 20, type: V1.HistoryType.bolusDone.rawValue, a: 0, b: 0)]
        link.nextEventID = 3
        _ = send(t, .getStatus)
        XCTAssertFalse(events.isEmpty)
        XCTAssertTrue(events.allSatisfy { $0 == .bolusCompleted(id: 1, deliveredPulses: 40) }, "bolus 2 was refused: no event may carry its id")
    }

    func test_acknowledgeCarriesTheMaskExplicitly() {
        let t = transport(phase: .faulted)
        _ = send(t, .silenceAlarm)
        XCTAssertEqual(link.requests(of: .acknowledge).first?.u16(.faultMask), 0xFFFF)
    }

    func test_everyCommandStartsWithTheTimeOfDay() {
        let t = transport(phase: .active)
        _ = send(t, .getStatus)
        _ = send(t, .bolus(id: 1, pulses: 1))
        for request in link.requests { XCTAssertEqual(request.tlvs.first?.tag, V1.Tag.timeOfDayMS.rawValue) }
    }

    func test_theHistoryStartAndTempStartEventsCarryTheirNumbers() {
        let t = transport(phase: .active)
        XCTAssertEqual(t.domainEvent(for: V1.HistoryEvent(id: 1, timeSeconds: 0, type: V1.HistoryType.tempStart.rawValue, a: 1_500, b: 30)),
                       .tempBasalStarted(rateTicks: 30, durationMinutes: 30))
        XCTAssertNil(t.domainEvent(for: V1.HistoryEvent(id: 1, timeSeconds: 0, type: V1.HistoryType.drawDone.rawValue, a: 19_994, b: 20_000)))
    }
}
