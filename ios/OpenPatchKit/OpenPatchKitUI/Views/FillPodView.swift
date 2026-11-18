import OpenPatchCore
import SwiftUI

/// Syringe fill step. The pod cannot measure what is injected, so the user confirms the amount.
struct FillPodView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    private var range: ClosedRange<Double> { PodSize.minimumFillUnits...model.podSize.capacityUnits }

    var body: some View {
        StepContainer(systemImage: "syringe", title: L("Fill the pod with insulin"), errorMessage: model.errorMessage,
                      primaryTitle: L("Pod is filled"), isBusy: model.isBusy, primaryAction: model.confirmFill) {
            VStack(alignment: .leading, spacing: 14) {
                NumberedInstruction(number: 1, text: L("Draw U100 insulin at room temperature into the syringe. Fill at least %.0f U.", PodSize.minimumFillUnits))
                NumberedInstruction(number: 2, text: L("Tap the syringe and push out all air bubbles."))
                NumberedInstruction(number: 3, text: L("Insert the needle straight into the fill port on the side of the pod."))
                NumberedInstruction(number: 4, text: L("Inject slowly until you have injected the amount below. Never exceed %.0f U.", model.podSize.capacityUnits))
                NumberedInstruction(number: 5, text: L("Enter exactly how much insulin you injected, then confirm."))
            }
            VStack(alignment: .leading) {
                Text(L("Injected amount"))
                    .font(.headline)
                Stepper(value: $model.fillUnits, in: range, step: 5) {
                    Text(L("%.0f U", model.fillUnits)).font(.title3.monospacedDigit().weight(.semibold))
                }
                .accessibilityLabel(L("Injected amount in units"))
                Text(L("Priming uses about %.1f U.", PumpConstants.primeUnits))
                    .font(.footnote).foregroundColor(.secondary)
            }
        }
        .onAppear { model.prepareRefillIfNeeded() }
    }
}
