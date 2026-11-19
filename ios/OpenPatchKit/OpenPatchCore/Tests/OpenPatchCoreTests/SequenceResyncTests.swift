import XCTest
@testable import OpenPatchCore

/// Sequence persistence and `LAST_SEQ` resync (docs/04-protocol.md section 6, v1 section 5.2): a plain-text pod drops every command whose
/// `seq` is not above its persisted maximum, silently. The phone must find its way back without ever repeating a write.
final class SequenceResyncTests: XCTestCase {
    private var link: WirePodLink!
    private var checkpoints: [V1Transport.Checkpoint] = []

    private func transport(initialSequence: UInt16) -> V1Transport {
        link = WirePodLink()
        checkpoints = []
        let t = V1Transport(link: link, initialPhase: .active, initialSequence: initialSequence, timeOfDayMilliseconds: { 0 })
        t.checkpointHandler = { [unowned self] in checkpoints.append($0) }
        return t
    }

    private func send(_ t: V1Transport, _ command: Command) -> Result<Response, TransportError> {
        var result: Result<Response, TransportError>!
        t.send(command) { result = $0 }
        return result
    }

    func test_aPhoneThatLostItsSequenceCounterFindsTheWayBackWithReadsOnly() {
        let t = transport(initialSequence: 1)
        link.lastAccepted = 100                       // the pod remembers 100, the phone starts at 1
        guard case .success(.ok) = send(t, .getStatus) else { return XCTFail("status never came back") }
        XCTAssertEqual(link.requests.map(\.seq).prefix(3), [1, 18, 275], "1 -> +16 -> +256")
        XCTAssertGreaterThan(link.lastAccepted, 100)
        // the next command is above everything the pod has seen
        _ = send(t, .getStatus)
        XCTAssertGreaterThan(link.requests.last!.seq, 275)
        XCTAssertGreaterThan(checkpoints.last!.nextSequence, link.lastAccepted, "persisted before it is used")
    }

    func test_aWriteIsNeverRepeatedAfterSilence() {
        let t = transport(initialSequence: 1)
        link.lastAccepted = 100
        XCTAssertEqual(send(t, .bolus(id: 1, pulses: 1)), .failure(.timeout))
        XCTAssertEqual(link.requests(of: .bolus).count, 1, "one frame, no blind retry of a delivery command")
    }

    func test_aReplayAnswerIsRefusedBeforeExecutionSoEvenAWriteMayBeResentWithAHigherSeq() {
        let t = transport(initialSequence: 1)
        link.lastAccepted = 100
        link.answersReplay = true
        guard case .success(.ok) = send(t, .setTempBasal(rateTicks: 20, durationMinutes: 30)) else { return XCTFail() }
        let temps = link.requests(of: .setTempBasal)
        XCTAssertEqual(temps.count, 3, "REPLAY at 1 and 18, accepted at 275")
        XCTAssertEqual(temps.map(\.seq), [1, 18, 275])
        XCTAssertEqual(link.lastAccepted >= 275, true)
    }

    func test_lastSeqInAStatusMovesAPhoneThatIsBehind() {
        let t = transport(initialSequence: 1)
        link.lastSeqOverride = 500           // the pod answers, but says it has seen up to 500 (a restored LAST_SEQ)
        _ = send(t, .getStatus)
        _ = send(t, .getStatus)
        XCTAssertEqual(link.requests.map(\.seq), [1, 501], "the next frame is above LAST_SEQ, not 2")
        XCTAssertEqual(checkpoints.last?.nextSequence, 502)
    }

    func test_aHealthyPodNeverCausesAJump() {
        let t = transport(initialSequence: 1)
        for _ in 0..<5 { _ = send(t, .getStatus) }
        XCTAssertEqual(link.requests.map(\.seq), [1, 2, 3, 4, 5])
    }

    func test_aSilentPodGivesUpAfterTheJumpsInsteadOfLooping() {
        let t = transport(initialSequence: 1)
        link.dropNext = 100
        XCTAssertEqual(send(t, .getStatus), .failure(.timeout))
        XCTAssertEqual(link.requests.count, 1 + V1Transport.resyncJumps.count)
    }

    func test_restoreMarginStillStartsAboveTheLastKnownSequence() {
        // what the manager does after a crash: persisted sequence + 16 (the host stores asynchronously)
        let t = transport(initialSequence: 60 + 16)
        link.lastAccepted = 70                        // the pod got up to 70, the persisted value was 60
        _ = send(t, .getStatus)
        XCTAssertEqual(link.requests.first!.seq, 76)
        XCTAssertEqual(link.requests.count, 1, "no resync needed")
    }
}
