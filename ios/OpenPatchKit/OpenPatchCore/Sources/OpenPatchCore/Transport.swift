import Foundation

public enum TransportError: Error, Equatable {
    case notConnected
    case timeout            // request may or may not have reached the pod
    case disconnected
    case bluetoothUnavailable
    case malformedResponse
    case mtuTooSmall        // protocol v1 needs an ATT MTU >= 247 (no fragmentation)
    case notPaired          // the pod has no pairing secret or another one (docs/04-protocol.md): pair again with the button
    case sessionFailed      // key agreement failed (wrong secret, altered exchange, pairing window closed)
}

/// Abstraction between the PumpManager and the radio. Speaks the app's domain `Command` / `Response`;
/// the wire format lives behind it (`V1Transport` for real pods, `SimulatedTransport` for tests).
public protocol OpenPatchTransport: AnyObject {
    var isConnected: Bool { get }
    /// Called for pod events. May be invoked from any queue.
    var eventHandler: ((PodEvent) -> Void)? { get set }
    func connect(completion: @escaping (Result<Void, TransportError>) -> Void)
    func disconnect()
    func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void)

    // MARK: Diagnostics (docs/06-diagnostics.md 5.5). Defaults answer "unsupported" until a transport implements them.

    /// All records from `from` on (paged until the pod's `NEXT_DIAG_ID`), with the latched set.
    func getFaultLog(from: UInt32, completion: @escaping (Result<FaultLog, DiagCommandError>) -> Void)
    func runSelfTest(_ kind: SelfTestState.Kind, completion: @escaping (Result<SelfTestState, DiagCommandError>) -> Void)
    /// `nil` clears every clearable W/F record. The pod, not the app, decides whether a latched code clears.
    func clearDiag(_ code: DiagCode?, completion: @escaping (Result<DiagSummary, DiagCommandError>) -> Void)
}

public extension OpenPatchTransport {
    func getFaultLog(from: UInt32, completion: @escaping (Result<FaultLog, DiagCommandError>) -> Void) {
        completion(.failure(.nack(.unsupported, code: nil)))
    }
    func runSelfTest(_ kind: SelfTestState.Kind, completion: @escaping (Result<SelfTestState, DiagCommandError>) -> Void) {
        completion(.failure(.nack(.unsupported, code: nil)))
    }
    func clearDiag(_ code: DiagCode?, completion: @escaping (Result<DiagSummary, DiagCommandError>) -> Void) {
        completion(.failure(.nack(.unsupported, code: nil)))
    }
}

public enum SimulatedTransportFault: Equatable {
    case dropRequest      // pod never sees the command
    case dropResponse     // pod executes the command, reply is lost
    case disconnect
}

/// Synchronous in-memory transport on top of `SimulatedPod`.
public final class SimulatedTransport: OpenPatchTransport {
    public let pod: SimulatedPod
    public private(set) var isConnected = false
    public var eventHandler: ((PodEvent) -> Void)?
    /// One-shot fault for the next `send`.
    public var fault: SimulatedTransportFault?

    public init(pod: SimulatedPod) { self.pod = pod }

    /// `false` simulates a pod that is out of range / switched off: connecting times out.
    public var isReachable = true

    public func connect(completion: @escaping (Result<Void, TransportError>) -> Void) {
        guard isReachable else { return completion(.failure(.timeout)) }
        isConnected = true
        completion(.success(()))
    }

    public func disconnect() { isConnected = false }

    public func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {
        guard isConnected, isReachable else { isConnected = false; return completion(.failure(.notConnected)) }
        let injected = fault
        fault = nil

        switch injected {
        case .dropRequest: return completion(.failure(.timeout))
        case .disconnect: isConnected = false; return completion(.failure(.disconnected))
        default: break
        }

        let response = pod.handle(command)
        forwardEvents()
        if injected == .dropResponse { return completion(.failure(.timeout)) }
        completion(.success(response))
    }

    private func diagnostics<T>(_ work: () -> Result<T, DiagCommandError>, completion: (Result<T, DiagCommandError>) -> Void) {
        guard isConnected, isReachable else { isConnected = false; return completion(.failure(.transport(.notConnected))) }
        guard pod.reportsDiagnostics else { return completion(.failure(.nack(.unsupported, code: nil))) }
        let result = work()
        forwardEvents()
        completion(result)
    }

    public func getFaultLog(from: UInt32, completion: @escaping (Result<FaultLog, DiagCommandError>) -> Void) {
        diagnostics({
            var log = pod.faultLog(from: from)
            var cursor = from
            while let last = log.records.last, last.recID + 1 < log.nextID, log.records.count < SimulatedDiagState.ringCapacity {
                cursor = last.recID + 1
                let page = pod.faultLog(from: cursor)
                guard !page.records.isEmpty else { break }
                log.records += page.records
            }
            _ = cursor
            return .success(log)
        }, completion: completion)
    }

    public func runSelfTest(_ kind: SelfTestState.Kind, completion: @escaping (Result<SelfTestState, DiagCommandError>) -> Void) {
        diagnostics({ pod.runSelfTest(kind) }, completion: completion)
    }

    public func clearDiag(_ code: DiagCode?, completion: @escaping (Result<DiagSummary, DiagCommandError>) -> Void) {
        diagnostics({ pod.clearDiag(code) }, completion: completion)
    }

    /// Advances simulated time and delivers resulting pod events.
    public func advance(by seconds: Int) {
        pod.advance(by: seconds)
        forwardEvents()
    }

    private func forwardEvents() {
        for event in pod.drainEvents() where isConnected { eventHandler?(event) }
    }
}
