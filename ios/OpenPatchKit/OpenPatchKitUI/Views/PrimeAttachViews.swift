import OpenPatchCore
import SwiftUI

struct PrimeView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    private var started: Bool { model.primeElapsed > 0 || model.isBusy }

    var body: some View {
        StepContainer(systemImage: "drop.fill", title: L("Dock and prime the pod"), errorMessage: model.errorMessage,
                      primaryTitle: started ? nil : L("Start priming"), isBusy: model.isBusy, primaryAction: model.startPrime) {
            Text(L("Place the pod on the bench dock whose outlet leads into the vial. Priming fills the outlet path with water and takes about %.0f seconds.", PumpConstants.primeDuration))
            if let attempt = model.primeTakeupAttempt {
                // after an assisted fill the pod first takes up the slack of its drive, a slice per prime command
                ProgressView(value: Double(attempt), total: Double(PumpConstants.primeTakeupMaxAttempts)) {
                    Text(L("Taking up the slack of the drive (%d of %d)...", attempt, PumpConstants.primeTakeupMaxAttempts))
                }
                Text(L("This can take a few minutes. Keep the pod on the dock and near the phone."))
                    .font(.footnote).foregroundColor(.secondary)
            } else if started {
                ProgressView(value: min(model.primeElapsed / PumpConstants.primeDuration, 1)) {
                    Text(L("Priming..."))
                }
                .accessibilityValue("\(Int(min(model.primeElapsed / PumpConstants.primeDuration, 1) * 100)) %")
            }
        }
    }
}

struct AttachView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        StepContainer(systemImage: "hand.tap.fill", title: L("Start the bench run"), errorMessage: model.errorMessage,
                      primaryTitle: L("Start water delivery"), isBusy: model.isBusy, primaryAction: model.activate) {
            VStack(alignment: .leading, spacing: 14) {
                NumberedInstruction(number: 1, text: L("Check that the pod sits on the bench dock and that its outlet leads into the vial on the balance."))
                NumberedInstruction(number: 2, text: L("Tare the balance now: the priming volume must not count."))
                NumberedInstruction(number: 3, text: L("Tap the button below to start the basal program. Only water is delivered."))
            }
            Label(L("If the pod is not seated on the dock, do not start delivery."), systemImage: "exclamationmark.triangle.fill")
                .font(.footnote).foregroundColor(.orange)
        }
    }
}
