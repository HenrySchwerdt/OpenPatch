import CoreBluetooth
import Foundation
import OpenPatchCore
import OpenPatchKit

/// Drives pairing -> fill -> prime -> attach (and the shorter refill path for a reusable pod).
final class OpenPatchSetupViewModel: ObservableObject {
    enum Step: Equatable { case size, pairing, fill, prime, attach, done }

    @Published var step: Step
    @Published var podSize: PodSize
    @Published var fillUnits: Double
    @Published var isBusy = false
    @Published var errorMessage: String?
    @Published var discovered: [DiscoveredPod] = []
    @Published var bluetoothUnavailable = false
    @Published var primeElapsed: TimeInterval = 0

    let manager: OpenPatchPumpManager
    let allowSimulator: Bool
    let isRefill: Bool
    var onPumpManagerCreated: () -> Void = {}
    var onFinished: () -> Void = {}
    var onCancel: () -> Void = {}

    private let scanner = OpenPatchBluetoothScanner()
    private var primeTimer: Timer?

    init(manager: OpenPatchPumpManager, allowSimulator: Bool, isRefill: Bool) {
        self.manager = manager
        self.allowSimulator = allowSimulator
        self.isRefill = isRefill
        let size = manager.state.podSize
        self.podSize = size
        self.fillUnits = size.capacityUnits
        self.step = isRefill ? .fill : .size
    }

    deinit { primeTimer?.invalidate() }

    // MARK: Step: size

    func confirmSize() {
        manager.selectPodSize(podSize)
        fillUnits = podSize.capacityUnits
        step = .pairing
        startScan()
    }

    // MARK: Step: pairing

    func startScan() {
        scanner.onUpdate = { [weak self] pods, state in
            DispatchQueue.main.async {
                self?.discovered = pods
                self?.bluetoothUnavailable = state == .unauthorized || state == .poweredOff || state == .unsupported
            }
        }
        scanner.start()
    }

    func pair(with pod: DiscoveredPod) {
        pair(identifier: pod.id, name: pod.name, simulated: false)
    }

    func pairSimulator() {
        pair(identifier: nil, name: "OpenPatch Simulator", simulated: true)
    }

    private func pair(identifier: UUID?, name: String, simulated: Bool) {
        scanner.stop()
        run { done in
            self.manager.pair(peripheralIdentifier: identifier, name: name, simulated: simulated) { error in
                done(error) {
                    self.onPumpManagerCreated()
                    self.step = .fill
                }
            }
        }
    }

    // MARK: Step: fill

    /// A removed (deactivated) pod must be woken with `hello` before it accepts a new fill.
    func prepareRefillIfNeeded() {
        guard isRefill, manager.state.phase == .deactivated else { return }
        run { done in
            self.manager.beginRefill { error in done(error) {} }
        }
    }

    func confirmFill() {
        run { done in
            self.manager.confirmFill(units: self.fillUnits) { error in
                done(error) { self.step = .prime }
            }
        }
    }

    // MARK: Step: prime

    func startPrime() {
        run { done in
            self.manager.startPrime { error in
                done(error) { self.beginPrimeProgress() }
            }
        }
    }

    private func beginPrimeProgress() {
        primeElapsed = 0
        primeTimer?.invalidate()
        primeTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
            guard let self else { return timer.invalidate() }
            self.primeElapsed += 1
            if self.manager.state.phase == .primed {
                timer.invalidate()
                self.step = .attach
            } else if Int(self.primeElapsed) % 3 == 0 {
                self.manager.refreshStatus { _ in }
            }
        }
    }

    // MARK: Step: attach

    func activate() {
        run { done in
            self.manager.activate { error in
                done(error) {
                    self.step = .done
                }
            }
        }
    }

    func finish() { onFinished() }

    func cancel() {
        scanner.stop()
        primeTimer?.invalidate()
        onCancel()
    }

    // MARK: Helpers

    /// Runs an async manager call with busy/error handling; `done` marshals back to the main queue.
    private func run(_ work: @escaping (@escaping (Error?, @escaping () -> Void) -> Void) -> Void) {
        errorMessage = nil
        isBusy = true
        work { error, onSuccess in
            DispatchQueue.main.async {
                self.isBusy = false
                if let error { self.errorMessage = error.localizedDescription } else { onSuccess() }
            }
        }
    }
}
