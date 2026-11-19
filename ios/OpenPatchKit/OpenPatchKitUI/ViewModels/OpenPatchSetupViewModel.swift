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
    /// Prime attempt while the pod takes up the lost motion of its drive (nil = not happening).
    @Published var primeTakeupAttempt: Int?
    /// Assisted fill: the pod's fill job as of the last status read, and whether the user started one.
    @Published var fillStatus: FillStatus?
    @Published var fillStarted = false

    let manager: OpenPatchPumpManager
    let allowSimulator: Bool
    let isRefill: Bool
    var onPumpManagerCreated: () -> Void = {}
    var onFinished: () -> Void = {}
    var onCancel: () -> Void = {}

    private let scanner = OpenPatchBluetoothScanner()
    private var primeTimer: Timer?
    private var fillTimer: Timer?
    private var fillPolling = false

    init(manager: OpenPatchPumpManager, allowSimulator: Bool, isRefill: Bool) {
        self.manager = manager
        self.allowSimulator = allowSimulator
        self.isRefill = isRefill
        let size = manager.state.podSize
        self.podSize = size
        self.fillUnits = size.capacityUnits
        self.step = isRefill ? .fill : .size
    }

    deinit { primeTimer?.invalidate(); fillTimer?.invalidate() }

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

    /// The drive of the pod behind this setup (known once it answered `hello`).
    var calibration: DriveCalibration? { manager.state.driveCalibration }

    /// `true` for every pod that has the assisted pressure fill (the cup pod: the ONLY way it is filled).
    var usesAssistedFill: Bool { calibration.map { $0.allowedFillModes.contains(.assistedPressure) } ?? false }

    /// Retraction rate of the pod during the fill, in U per second (what the user has to match with the syringe).
    var fillUnitsPerSecond: Double { calibration?.assistedFillUnitsPerSecond ?? 0 }

    /// Legacy pods (C reference): the user injected by hand and confirms the amount.
    func confirmFill() {
        run { done in
            self.manager.confirmFill(units: self.fillUnits) { error in
                done(error) { self.step = .prime }
            }
        }
    }

    /// Assisted pressure fill: the pod starts retracting; the user pushes the syringe at the same pace.
    func startAssistedFill() {
        setSimulatedPodDocked(false)
        fillStatus = nil
        run { done in
            self.manager.startFill(mode: .assistedPressure, units: self.fillUnits) { error in
                done(error) {
                    self.fillStarted = true
                    self.beginFillPolling()
                }
            }
        }
    }

    func cancelAssistedFill() {
        run { done in
            self.manager.cancelFill { error in done(error) { self.pollFillOnce() } }
        }
    }

    /// The fill ended (done, stalled or cancelled) with something in the reservoir: go on to the prime.
    func continueAfterFill() {
        stopFillPolling()
        step = .prime
    }

    /// Starts over after a stall or a cancel (the remaining volume is asked for again).
    func fillMore() {
        fillStarted = false
        fillStatus = nil
        let drawn = manager.state.fill?.drawnUnits ?? 0
        fillUnits = max(min(fillUnits - drawn, podSize.capacityUnits - drawn), PodSize.minimumFillUnits)
    }

    private func beginFillPolling() {
        fillTimer?.invalidate()
        fillTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
            guard let self else { return timer.invalidate() }
            self.pollFillOnce()
        }
    }

    private func stopFillPolling() { fillTimer?.invalidate(); fillTimer = nil }

    private func pollFillOnce() {
        guard !fillPolling else { return }
        fillPolling = true
        manager.refreshStatus { [weak self] error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.fillPolling = false
                self.fillStatus = self.manager.state.fill
                if let status = self.fillStatus, !status.isRunning, status.state != .idle { self.stopFillPolling() }
                if let error, self.fillStatus?.isRunning != true { self.errorMessage = error.localizedDescription }
            }
        }
    }

    /// The in-app simulated pod has a dock input: the assisted fill needs it OFF, the prime needs it ON (a real pod is moved by hand).
    private func setSimulatedPodDocked(_ docked: Bool) {
        guard manager.state.usesSimulatedPod else { return }
        let role = manager.state.podRole
        (role.flatMap { OpenPatchSimulator.shared.pod(for: $0) } ?? OpenPatchSimulator.shared.pod)?.setDocked(docked)
    }

    // MARK: Step: prime

    func startPrime() {
        setSimulatedPodDocked(true)
        // The progress runs from the tap on: after an assisted fill the pod first takes up the slack of its drive over several
        // prime commands (minutes), and the screen has to say so.
        beginPrimeProgress()
        run { done in
            self.manager.startPrime { error in
                if error != nil {
                    DispatchQueue.main.async { self.primeTimer?.invalidate(); self.primeElapsed = 0; self.primeTakeupAttempt = nil }
                }
                done(error) {}
            }
        }
    }

    private func beginPrimeProgress() {
        primeElapsed = 0
        primeTimer?.invalidate()
        primeTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] timer in
            guard let self else { return timer.invalidate() }
            self.primeElapsed += 1
            self.primeTakeupAttempt = self.manager.state.primeTakeupAttempt
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
        stopFillPolling()
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
