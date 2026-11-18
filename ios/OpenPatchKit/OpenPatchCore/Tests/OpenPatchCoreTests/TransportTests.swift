import XCTest
@testable import OpenPatchCore

final class TransportTests: XCTestCase {
    private let t0 = Date(timeIntervalSince1970: 1_800_000_000)

    private func makeTransport() -> (SimulatedTransport, SimulatedPod) {
        let pod = SimulatedPod(size: .u100, startDate: t0)
        return (SimulatedTransport(pod: pod), pod)
    }

    func test_sendBeforeConnect_fails() {
        let (transport, _) = makeTransport()
        var result: Result<Response, TransportError>?
        transport.send(.getStatus) { result = $0 }
        XCTAssertEqual(result, .failure(.notConnected))
    }

    func test_connectSendDisconnect() {
        let (transport, _) = makeTransport()
        transport.connect { _ in }
        XCTAssertTrue(transport.isConnected)
        var result: Result<Response, TransportError>?
        transport.send(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)) { result = $0 }
        guard case .success(.ok(let status))? = result else { return XCTFail("\(String(describing: result))") }
        XCTAssertEqual(status.phase, .paired)
        transport.disconnect()
        XCTAssertFalse(transport.isConnected)
    }

    func test_injectedTimeout_surfacesAsUncertainOutcome() {
        let (transport, pod) = makeTransport()
        transport.connect { _ in }
        transport.fault = .dropResponse      // pod executes, reply lost
        var result: Result<Response, TransportError>?
        transport.send(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)) { result = $0 }
        XCTAssertEqual(result, .failure(.timeout))
        XCTAssertEqual(pod.phase, .paired, "the command did reach the pod")
    }

    func test_injectedRequestLoss_neverReachesPod() {
        let (transport, pod) = makeTransport()
        transport.connect { _ in }
        transport.fault = .dropRequest
        var result: Result<Response, TransportError>?
        transport.send(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)) { result = $0 }
        XCTAssertEqual(result, .failure(.timeout))
        XCTAssertEqual(pod.phase, .unpaired)
    }

    func test_faultIsOneShot() {
        let (transport, _) = makeTransport()
        transport.connect { _ in }
        transport.fault = .dropRequest
        transport.send(.getStatus) { _ in }
        var result: Result<Response, TransportError>?
        transport.send(.getStatus) { result = $0 }
        guard case .success? = result else { return XCTFail() }
    }

    func test_podEvents_areForwardedToHandler() throws {
        let (transport, pod) = makeTransport()
        transport.connect { _ in }
        var received: [PodEvent] = []
        transport.eventHandler = { received.append($0) }
        transport.send(.hello(protocolVersion: 1, time: t0, utcOffsetMinutes: 0)) { _ in }
        transport.send(.confirmFill(pulses: 1000)) { _ in }
        transport.send(.prime) { _ in }
        transport.advance(by: Int(PumpConstants.primeDuration) + 1)
        XCTAssertEqual(received, [.primeCompleted])
        XCTAssertEqual(pod.phase, .primed)
    }
}
