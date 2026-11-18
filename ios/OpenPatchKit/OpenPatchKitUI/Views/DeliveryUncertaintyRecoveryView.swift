import LoopKitUI
import OpenPatchKit
import SwiftUI
import UIKit

struct DeliveryUncertaintyRecoveryView: View {
    let appName: String
    let since: Date
    let retry: (@escaping (Error?) -> Void) -> Void
    let acknowledge: () -> Void
    @State private var message: String?
    @State private var busy = false

    var body: some View {
        StepContainer(systemImage: "exclamationmark.triangle.fill", title: L("Delivery status uncertain"), errorMessage: message,
                      primaryTitle: L("Check pod again"), isBusy: busy, primaryAction: check) {
            Text(L("%@ lost contact with the pod while changing insulin delivery (%@). The pod may or may not have executed the command.", appName, since.formatted(date: .omitted, time: .shortened)))
            Text(L("Move your phone close to the pod and check again. If you cannot reach the pod, check your glucose and treat as needed."))
            Button(L("I checked the pod and my glucose - continue"), role: .destructive, action: acknowledge)
        }
    }

    private func check() {
        busy = true
        message = nil
        retry { error in
            DispatchQueue.main.async {
                busy = false
                if let error { message = error.localizedDescription } else { acknowledge() }
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
                                                             acknowledge: {}))
        rootView = DeliveryUncertaintyRecoveryView(appName: appName, since: since,
                                                   retry: { manager.refreshStatus(completion: $0) },
                                                   acknowledge: { [weak self] in
            manager.clearDeliveryUncertainty()
            guard let self else { return }
            self.completionDelegate?.completionNotifyingDidComplete(self)
        })
        isModalInPresentation = true
    }

    @MainActor required dynamic init?(coder aDecoder: NSCoder) { fatalError("init(coder:) is not supported") }
}
