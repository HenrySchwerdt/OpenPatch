import Foundation
import OpenPatchCore

/// Process-wide simulated pod for development on the iOS Simulator (no Bluetooth there) and for demos.
/// Time runs in real time (1 simulated second per real second).
public final class OpenPatchSimulator {
    public static let shared = OpenPatchSimulator()
    private var transport: SimulatedTransport?
    private var timer: DispatchSourceTimer?
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

    public func reset() {
        queue.sync { timer?.cancel(); timer = nil; transport = nil }
    }
}
