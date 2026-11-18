import OpenPatchCore
import SwiftUI

struct PrimeView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    private var started: Bool { model.primeElapsed > 0 || model.isBusy }

    var body: some View {
        StepContainer(systemImage: "drop.fill", title: L("Prime the pod"), errorMessage: model.errorMessage,
                      primaryTitle: started ? nil : L("Start priming"), isBusy: model.isBusy, primaryAction: model.startPrime) {
            Text(L("Hold the pod with the needle pointing up and away from you. Priming fills the needle with insulin and takes about %.0f seconds.", PumpConstants.primeDuration))
            if started {
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
        StepContainer(systemImage: "hand.tap.fill", title: L("Attach the pod"), errorMessage: model.errorMessage,
                      primaryTitle: L("Start insulin delivery"), isBusy: model.isBusy, primaryAction: model.activate) {
            VStack(alignment: .leading, spacing: 14) {
                NumberedInstruction(number: 1, text: L("Make sure the cannula (Accu-Chek Insight Flex) is inserted and the adhesive pad with the Velcro patch is in place."))
                NumberedInstruction(number: 2, text: L("Align the pod with the cannula head and press it on until both side clips click."))
                NumberedInstruction(number: 3, text: L("Press the pod onto the Velcro patch and check that it sits firmly."))
                NumberedInstruction(number: 4, text: L("Tap the button below to start your basal program."))
            }
            Label(L("If the pod does not click in place, do not start delivery."), systemImage: "exclamationmark.triangle.fill")
                .font(.footnote).foregroundColor(.orange)
        }
    }
}
