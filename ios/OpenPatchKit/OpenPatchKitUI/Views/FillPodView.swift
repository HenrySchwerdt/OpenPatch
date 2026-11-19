import OpenPatchCore
import SwiftUI

/// Refill step. BENCH ONLY: water.
///
/// Pods with the assisted fill (the cup pod, which has no check valve and never draws by itself) are filled with the assisted
/// PRESSURE fill: the user pushes a water-filled syringe through the septum while the pod retracts its plunger at a fixed rate.
/// Only legacy pods (C reference) keep the old "inject by hand and confirm the amount" step.
struct FillPodView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        Group {
            if model.usesAssistedFill { AssistedFillView(model: model) } else { ManualFillView(model: model) }
        }
        .onAppear { model.prepareRefillIfNeeded() }
    }
}

struct AssistedFillView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    private var range: ClosedRange<Double> { PodSize.minimumFillUnits...model.podSize.capacityUnits }
    private var millilitres: Double { model.fillUnits / 100 }   // U100: 1 U = 10 ul

    var body: some View {
        if let fill = model.fillStatus, model.fillStarted {
            progress(fill)
        } else {
            instructions
        }
    }

    private var instructions: some View {
        StepContainer(systemImage: "syringe", title: L("Fill the pod with water"), errorMessage: model.errorMessage,
                      primaryTitle: model.fillStarted ? L("Starting...") : L("Start filling"), isBusy: model.isBusy || model.fillStarted,
                      primaryAction: model.startAssistedFill) {
            Label(L("Bench test: WATER only. Never insulin or any other drug."), systemImage: "drop.triangle.fill")
                .font(.callout.weight(.semibold)).foregroundColor(.orange)
            VStack(alignment: .leading, spacing: 14) {
                NumberedInstruction(number: 1, text: L("Draw at least %.2f ml of water into the syringe. Push out all air bubbles.", PodSize.minimumFillUnits / 100))
                NumberedInstruction(number: 2, text: L("Make sure the pod is OFF the dock: it only retracts its plunger while it is undocked."))
                NumberedInstruction(number: 3, text: L("Insert the needle straight into the fill septum of the pod and hold the syringe still."))
                NumberedInstruction(number: 4, text: L("Choose how much water to fill, then tap Start filling."))
                NumberedInstruction(number: 5, text: L("The pod now retracts its plunger by itself, at about %.1f U per second. Push the syringe plunger slowly at the same pace. The pod never draws by itself: if you do not push, nothing enters.", model.fillUnitsPerSecond))
            }
            VStack(alignment: .leading) {
                Text(L("Amount of water"))
                    .font(.headline)
                Stepper(value: $model.fillUnits, in: range, step: 5) {
                    Text(L("%.0f U (%.2f ml)", model.fillUnits, millilitres)).font(.title3.monospacedDigit().weight(.semibold))
                }
                .accessibilityLabel(L("Amount of water in units"))
                Text(L("The first priming uses about %.1f U and the drive takes up its slack first (about 2 to 3 U).", PumpConstants.primeUnits))
                    .font(.footnote).foregroundColor(.secondary)
            }
        }
    }

    private func progress(_ fill: FillStatus) -> some View {
        let ended = !fill.isRunning
        let drawn = fill.drawnUnits
        return StepContainer(systemImage: ended ? "checkmark.circle" : "arrow.down.to.line", title: title(fill), errorMessage: model.errorMessage,
                             primaryTitle: ended && drawn > 0 ? L("Continue to priming") : nil, isBusy: model.isBusy,
                             primaryAction: model.continueAfterFill) {
            ProgressView(value: fill.progress) {
                Text(L("%.1f of %.0f U", drawn, fill.requestedUnits))
            }
            .accessibilityValue("\(Int(fill.progress * 100)) %")
            if fill.isRunning {
                Text(L("Push the syringe plunger slowly now, at the same pace as the pod retracts. Stop pushing when the bar is full."))
                Button(L("Stop filling"), role: .destructive, action: model.cancelAssistedFill).disabled(model.isBusy)
            } else {
                Text(summary(fill))
                if fill.state != .done {
                    Button(L("Fill more"), action: model.fillMore)
                }
            }
        }
    }

    private func title(_ fill: FillStatus) -> String {
        switch fill.state {
        case .idle, .drawing: return L("Filling...")
        case .done: return L("Filled")
        case .stalled: return L("The plunger stopped")
        case .aborted: return L("Filling stopped")
        }
    }

    private func summary(_ fill: FillStatus) -> String {
        switch fill.state {
        case .done: return L("The pod now holds %.1f U of water. Remove the syringe.", fill.drawnUnits)
        case .stalled: return L("The pod's plunger hit its stop after %.1f U (asked for %.0f U). Remove the syringe. You can continue with this amount or fill more.", fill.drawnUnits, fill.requestedUnits)
        default: return L("The fill was stopped after %.1f U. Remove the syringe. You can continue with this amount or fill more.", fill.drawnUnits)
        }
    }
}

/// Legacy pods only.
struct ManualFillView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    private var range: ClosedRange<Double> { PodSize.minimumFillUnits...model.podSize.capacityUnits }

    var body: some View {
        StepContainer(systemImage: "syringe", title: L("Fill the pod with water"), errorMessage: model.errorMessage,
                      primaryTitle: L("Pod is filled"), isBusy: model.isBusy, primaryAction: model.confirmFill) {
            Label(L("Bench test: WATER only. Never insulin or any other drug."), systemImage: "drop.triangle.fill")
                .font(.callout.weight(.semibold)).foregroundColor(.orange)
            VStack(alignment: .leading, spacing: 14) {
                NumberedInstruction(number: 1, text: L("Draw at least %.2f ml of water into the syringe. Push out all air bubbles.", PodSize.minimumFillUnits / 100))
                NumberedInstruction(number: 2, text: L("Insert the needle straight into the fill port on the side of the pod."))
                NumberedInstruction(number: 3, text: L("Inject slowly until you have injected the amount below. Never exceed %.0f U.", model.podSize.capacityUnits))
                NumberedInstruction(number: 4, text: L("Enter exactly how much water you injected, then confirm."))
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
    }
}
