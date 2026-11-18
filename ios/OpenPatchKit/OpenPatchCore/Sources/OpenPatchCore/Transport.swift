import Foundation

public enum TransportError: Error, Equatable {
    case notConnected
    case timeout            // request may or may not have reached the pod
    case disconnected
    case bluetoothUnavailable
    case malformedResponse
    case mtuTooSmall        // protocol v1 needs an ATT MTU >= 247 (no fragmentation)
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

    public func connect(completion: @escaping (Result<Void, TransportError>) -> Void) {
        isConnected = true
        completion(.success(()))
    }

    public func disconnect() { isConnected = false }

    public func send(_ command: Command, completion: @escaping (Result<Response, TransportError>) -> Void) {
        guard isConnected else { return completion(.failure(.notConnected)) }
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

    /// Advances simulated time and delivers resulting pod events.
    public func advance(by seconds: Int) {
        pod.advance(by: seconds)
        forwardEvents()
    }

    private func forwardEvents() {
        for event in pod.drainEvents() where isConnected { eventHandler?(event) }
    }
}
