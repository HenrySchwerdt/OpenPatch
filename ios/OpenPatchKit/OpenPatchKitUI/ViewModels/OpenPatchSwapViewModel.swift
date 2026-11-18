import CoreBluetooth
import Foundation
import OpenPatchCore
import OpenPatchKit

/// "Swap pod" and spare-pod management for the A/B pair. All rules live in `PairSwapCoordinator`; this model only
/// shows the current phase, offers the actions that are legal in it and keeps the user informed.
final class OpenPatchSwapViewModel: ObservableObject {
    @Published private(set) var pair: PodPairState?
    @Published var isBusy = false
    @Published var errorMessage: String?
    @Published var confirmRemoval = false
    @Published var discovered: [DiscoveredPod] = []
    @Published var bluetoothUnavailable = false
    @Published var spareFillUnits: Double = 100

    let manager: OpenPatchPumpManager
    let allowSimulator: Bool
    var onClose: () -> Void = {}
    private let scanner = OpenPatchBluetoothScanner()

    init(manager: OpenPatchPumpManager, allowSimulator: Bool) {
        self.manager = manager
        self.allowSimulator = allowSimulator
        self.pair = manager.state.pair
        spareFillUnits = (manager.state.pair?.spare.flatMap { manager.state.pair?.record($0) }?.size ?? manager.state.podSize).capacityUnits
    }

    var phase: SwapPhase { pair?.phase ?? .idle }
    var hasSpare: Bool { pair.map { $0.pods.count == 2 } ?? false }

    func record(_ role: PodRole) -> PodRecord? { pair?.record(role) }

    func reload() { DispatchQueue.main.async { self.pair = self.manager.state.pair } }

    // MARK: Text

    var title: String {
        switch phase {
        case .idle: return L("Swap pod")
        case .releasingOld, .oldPodUnconfirmed: return L("Stopping the old pod")
        case .awaitingDock: return L("Dock the new pod")
        case .activatingNew: return L("Starting the new pod")
        case .priming: return L("Priming the cannula connector")
        case .primeUncertain: return L("Priming status unknown")
        case .resuming: return L("Starting insulin delivery")
        }
    }

    var instruction: String {
        let old = pair?.oldRole?.label ?? "-", new = pair?.newRole?.label ?? "-"
        switch phase {
        case .idle:
            return L("The active pod is replaced by the spare pod. The spare is checked first; if it is not ready nothing changes.")
        case .releasingOld:
            return L("Pod %@ is being told to stop. Stay close to it.", old)
        case .oldPodUnconfirmed:
            return L("Pod %@ did not confirm that it stopped. Try again, or - if you have taken it off the cannula - confirm that it is physically removed. The new pod does not start before one of the two.", old)
        case .awaitingDock:
            return L("Pod %@ has stopped. Take it off the cannula, put pod %@ on the cannula adapter and press Continue.", old, new)
        case .activatingNew:
            return L("Pod %@ is being started with your basal program. If the connection drops, press Continue: the pod is never started twice.", new)
        case .priming:
            return L("Only the connector between pod %@ and the cannula is filled. The cannula itself is NOT primed.", new)
        case .primeUncertain:
            return L("The connection dropped while priming. Priming twice pushes a little more insulin into the connector. Choose: prime again, or continue without.")
        case .resuming:
            return L("Pod %@ is primed. Press Continue to start insulin delivery.", new)
        }
    }

    // MARK: Actions

    func begin() { run { self.manager.beginSwap(completion: $0) } }
    func continueSwap() { run { self.manager.continueSwap(completion: $0) } }
    func retryPrime() { run { self.manager.retryUncertainPrime(completion: $0) } }

    func skipPrime() {
        if let error = manager.skipUncertainPrime() { errorMessage = error.localizedDescription } else { reload(); continueSwap() }
    }

    func confirmOldPodRemoved() {
        if let error = manager.confirmOldPodPhysicallyRemoved() { errorMessage = error.localizedDescription }
        confirmRemoval = false
        reload()
    }

    func takeOldPodBack() {
        if let error = manager.reactivateOldPod() { errorMessage = error.localizedDescription }
        reload()
    }

    // MARK: Spare pod

    func startScan() {
        scanner.onUpdate = { [weak self] pods, state in
            DispatchQueue.main.async {
                self?.discovered = pods
                self?.bluetoothUnavailable = state == .unauthorized || state == .poweredOff || state == .unsupported
            }
        }
        scanner.start()
    }

    func stopScan() { scanner.stop() }

    func pairSpare(with pod: DiscoveredPod) { pairSpare(identifier: pod.id, name: pod.name, simulated: false) }
    func pairSpareSimulator() { pairSpare(identifier: nil, name: "OpenPatch Simulator B", simulated: true) }

    private func pairSpare(identifier: UUID?, name: String, simulated: Bool) {
        scanner.stop()
        run { self.manager.pairSparePod(peripheralIdentifier: identifier, name: name, simulated: simulated, completion: $0) }
    }

    func fillSpare() { run { self.manager.fillSparePod(units: self.spareFillUnits, completion: $0) } }
    func refreshSpare() { run { self.manager.refreshSparePod(completion: $0) } }

    private func run(_ work: @escaping (@escaping (Error?) -> Void) -> Void) {
        errorMessage = nil
        isBusy = true
        work { error in
            DispatchQueue.main.async {
                self.isBusy = false
                self.pair = self.manager.state.pair
                self.errorMessage = error?.localizedDescription
            }
        }
    }
}
