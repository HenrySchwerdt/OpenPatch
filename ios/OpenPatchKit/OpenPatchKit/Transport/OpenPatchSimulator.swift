import Foundation
import OpenPatchCore

/// Process-wide simulated pod for development on the iOS Simulator (no Bluetooth there) and for demos.
/// Time runs in real time (1 simulated second per real second).
public final class OpenPatchSimulator {
    public static let shared = OpenPatchSimulator()
    private var transport: SimulatedTransport?
    private var timer: DispatchSourceTimer?
    /// Two-pod mode: one simulated pod per role (A and B), each with its own clock.
    private var pairTransports: [PodRole: SimulatedTransport] = [:]
    private var pairTimers: [PodRole: DispatchSourceTimer] = [:]
    private let queue = DispatchQueue(label: "org.openpatch.simulator")

    public var pod: SimulatedPod? { queue.sync { transport?.pod } }

    public func makeTransport(size: PodSize) -> OpenPatchTransport {
        queue.sync {
            if let transport, transport.pod.size == size { return transport }
            let pod = SimulatedPod(size: size, startDate: Date())
            let new = SimulatedTransport(pod: pod)
            transport = new
            timer?.cancel()
            let source = DispatchSource.makeTimerSource(queue: queue)
            source.schedule(deadline: .now() + 1, repeating: 1)
            source.setEventHandler { [weak new] in new?.advance(by: 1) }
            source.resume()
            timer = source
            return new
        }
    }

    /// Simulated pod for one role of the pair.
    public func makeTransport(size: PodSize, role: PodRole) -> OpenPatchTransport {
        queue.sync {
            if let existing = pairTransports[role], existing.pod.size == size { return existing }
            let new = SimulatedTransport(pod: SimulatedPod(size: size, startDate: Date()))
            pairTransports[role] = new
            pairTimers[role]?.cancel()
            let source = DispatchSource.makeTimerSource(queue: queue)
            source.schedule(deadline: .now() + 1, repeating: 1)
            source.setEventHandler { [weak new] in new?.advance(by: 1) }
            source.resume()
            pairTimers[role] = source
            return new
        }
    }

    public func pod(for role: PodRole) -> SimulatedPod? { queue.sync { pairTransports[role]?.pod } }

    public func reset() {
        queue.sync {
            timer?.cancel(); timer = nil; transport = nil
            pairTimers.values.forEach { $0.cancel() }
            pairTimers = [:]; pairTransports = [:]
        }
    }
}
