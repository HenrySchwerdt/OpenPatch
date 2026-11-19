import LoopKitUI
import OpenPatchKit
import SwiftUI
import UIKit

struct DeliveryUncertaintyRecoveryView: View {
    let appName: String
    let since: Date
    let retry: (@escaping (Error?) -> Void) -> Void
    /// The pump manager found out what the pod did (it reads the status and history on its own after a lost reply).
    let isResolved: () -> Bool
    let acknowledge: () -> Void
    @State private var message: String?
    @State private var busy = false

    var body: some View {
        StepContainer(systemImage: "exclamationmark.triangle.fill", title: L("Delivery status uncertain"), errorMessage: message,
                      primaryTitle: L("Check pod again"), isBusy: busy, primaryAction: check) {
            Text(L("%@ lost contact with the pod while changing delivery (%@). The pod may or may not have executed the command.", appName, since.formatted(date: .omitted, time: .shortened)))
            Text(L("The pump reads the pod again on its own and decides from the pod's history. Move your phone close to the pod and check again."))
            Button(L("I checked the pod - continue anyway"), role: .destructive, action: acknowledge)
        }
    }

    private func check() {
        busy = true
        message = nil
        retry { error in
            DispatchQueue.main.async {
                busy = false
                if let error { message = error.localizedDescription }
                else if isResolved() { acknowledge() }
                else { message = L("The pod's history could not be read completely, so the outcome is still unknown.") }
            }
        }
    }
}

final class OpenPatchRecoveryViewController: UIHostingController<DeliveryUncertaintyRecoveryView>, CompletionNotifying {
    weak var completionDelegate: CompletionDelegate?

    init(manager: OpenPatchPumpManager, appName: String) {
        let since = manager.state.deliveryUncertainSince ?? Date()
        super.init(rootView: DeliveryUncertaintyRecoveryView(appName: appName, since: since,
                                                             retry: { manager.refreshStatus(completion: $0) },
                                                             isResolved: { manager.state.deliveryUncertainSince == nil },
                                                             acknowledge: {}))
        rootView = DeliveryUncertaintyRecoveryView(appName: appName, since: since,
                                                   retry: { manager.refreshStatus(completion: $0) },
                                                   isResolved: { manager.state.deliveryUncertainSince == nil },
                                                   acknowledge: { [weak self] in
            manager.clearDeliveryUncertainty()
            guard let self else { return }
            self.completionDelegate?.completionNotifyingDidComplete(self)
        })
        isModalInPresentation = true
    }

    @MainActor required dynamic init?(coder aDecoder: NSCoder) { fatalError("init(coder:) is not supported") }
}
