import LoopKit
import LoopKitUI
import OpenPatchKit
import SwiftUI
import UIKit

/// Hosts the SwiftUI setup flow or the settings screen. Subclassing `PumpManagerSettingsNavigationViewController`
/// gives us `CompletionNotifying` and `PumpManagerOnboarding` for free.
final class OpenPatchUICoordinator: PumpManagerSettingsNavigationViewController {
    enum Mode { case setup, settings }

    private let manager: OpenPatchPumpManager
    private let mode: Mode

    init(manager: OpenPatchPumpManager, mode: Mode, colorPalette: LoopUIColorPalette,
         allowDebugFeatures: Bool, allowedInsulinTypes: [InsulinType]) {
        self.manager = manager
        self.mode = mode
        super.init(nibName: nil, bundle: nil)

        switch mode {
        case .setup:
            let model = OpenPatchSetupViewModel(manager: manager, allowSimulator: allowDebugFeatures, isRefill: false)
            model.onPumpManagerCreated = { [weak self] in
                guard let self else { return }
                self.pumpManagerOnboardingDelegate?.pumpManagerOnboarding(didCreatePumpManager: self.manager)
            }
            model.onFinished = { [weak self] in
                guard let self else { return }
                self.pumpManagerOnboardingDelegate?.pumpManagerOnboarding(didOnboardPumpManager: self.manager)
                self.notifyComplete()
            }
            model.onCancel = { [weak self] in self?.notifyComplete() }
            setViewControllers([host(OpenPatchSetupFlowView(model: model), colorPalette: colorPalette, modal: true)], animated: false)
        case .settings:
            let model = OpenPatchSettingsViewModel(manager: manager, allowSimulator: allowDebugFeatures)
            model.onDismiss = { [weak self] in self?.notifyComplete() }
            setViewControllers([host(OpenPatchSettingsView(model: model), colorPalette: colorPalette, modal: false)], animated: false)
        }
        navigationBar.prefersLargeTitles = true
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) is not supported") }

    private func host<V: View>(_ view: V, colorPalette: LoopUIColorPalette, modal: Bool) -> UIViewController {
        let controller = DismissibleHostingController(content: view, isModalInPresentation: modal, colorPalette: colorPalette)
        controller.navigationItem.backButtonDisplayMode = .generic
        return controller
    }
}
