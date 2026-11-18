import Foundation
import LoopKit
import OpenPatchCore
import OpenPatchKit

final class OpenPatchSettingsViewModel: ObservableObject, PumpManagerStatusObserver {
    @Published private(set) var state: OpenPatchPumpManagerState
    @Published var isBusy = false
    @Published var errorMessage: String?
    @Published var showRefill = false
    @Published var confirmRemoval = false
    @Published var showSwap = false

    let manager: OpenPatchPumpManager
    let allowSimulator: Bool
    var onDismiss: () -> Void = {}

    init(manager: OpenPatchPumpManager, allowSimulator: Bool) {
        self.manager = manager
        self.allowSimulator = allowSimulator
        self.state = manager.state
        manager.addStatusObserver(self, queue: .main)
    }

    deinit { manager.removeStatusObserver(self) }

    func pumpManager(_ pumpManager: PumpManager, didUpdate status: PumpManagerStatus, oldStatus: PumpManagerStatus) {
        state = manager.state
    }

    var reservoirText: String {
        guard let units = state.reservoirUnits else { return "-" }
        return L("%.1f of %.0f U", units, state.podSize.capacityUnits)
    }

    var batteryText: String {
        state.batteryFraction.map { "\(Int($0 * 100)) %" } ?? "-"
    }

    var phaseText: String {
        switch state.phase {
        case .unpaired: return L("Not paired")
        case .paired: return L("Paired, empty")
        case .filled: return L("Filled")
        case .priming: return L("Priming")
        case .primed: return L("Ready to attach")
        case .active: return L("Delivering insulin")
        case .suspended: return L("Insulin delivery suspended")
        case .faulted: return L("Error")
        case .deactivated: return L("Removed (can be refilled)")
        }
    }

    func refresh() {
        perform { done in self.manager.refreshStatus(completion: done) }
    }

    func suspendOrResume() {
        if state.phase == .suspended {
            perform { done in self.manager.resumeDelivery(completion: done) }
        } else {
            perform { done in self.manager.suspendDelivery(completion: done) }
        }
    }

    func deactivatePod() {
        perform { done in self.manager.deactivatePod(completion: done) }
    }

    func removePump() {
        perform { done in
            self.manager.prepareForDeactivation { error in
                done(error)
                if error == nil { DispatchQueue.main.async { self.onDismiss() } }
            }
        }
    }

    func makeSwapModel() -> OpenPatchSwapViewModel {
        let model = OpenPatchSwapViewModel(manager: manager, allowSimulator: allowSimulator)
        model.onClose = { [weak self] in self?.showSwap = false; self?.state = self?.manager.state ?? OpenPatchPumpManagerState() }
        return model
    }

    /// Separate reservoir / battery / wear / dock state of each pod; `nil` before the first pod is paired.
    var pods: [PodRecord] { (state.pair?.pods ?? []).sorted { $0.role.rawValue < $1.role.rawValue } }
    var activeRole: PodRole? { state.pair?.active }

    func makeRefillModel() -> OpenPatchSetupViewModel {
        let model = OpenPatchSetupViewModel(manager: manager, allowSimulator: allowSimulator, isRefill: true)
        model.onFinished = { [weak self] in self?.showRefill = false; self?.state = self?.manager.state ?? OpenPatchPumpManagerState() }
        model.onCancel = { [weak self] in self?.showRefill = false }
        return model
    }

    private func perform(_ work: @escaping (@escaping (Error?) -> Void) -> Void) {
        errorMessage = nil
        isBusy = true
        work { error in
            DispatchQueue.main.async {
                self.isBusy = false
                self.state = self.manager.state
                self.errorMessage = error?.localizedDescription
            }
        }
    }
}
