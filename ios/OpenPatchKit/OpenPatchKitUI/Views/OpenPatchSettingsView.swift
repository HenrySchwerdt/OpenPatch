import OpenPatchCore
import SwiftUI

struct OpenPatchSettingsView: View {
    @ObservedObject var model: OpenPatchSettingsViewModel

    var body: some View {
        List {
            if model.state.deliveryUncertainSince != nil {
                Section {
                    Label(L("Delivery status is uncertain. The pump is checking the pod."), systemImage: "exclamationmark.circle.fill")
                        .foregroundColor(.red)
                }
            }
            statusSection
            driveSection
            deliverySection
            podSection
            pairSection
            Section {
                Button(role: .destructive) { model.confirmRemoval = true } label: { Text(L("Remove OpenPatch from this app")) }
            }
            if let error = model.errorMessage {
                Section { Text(error).foregroundColor(.red) }
            }
        }
        .navigationTitle("OpenPatch")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) { Button(L("Done"), action: model.onDismiss) }
        }
        .sheet(isPresented: $model.showSwap) {
            OpenPatchSwapView(model: model.makeSwapModel())
        }
        .sheet(isPresented: $model.showRefill) {
            OpenPatchSetupFlowView(model: model.makeRefillModel())
        }
        .alert(isPresented: $model.confirmRemoval) {
            Alert(title: Text(L("Remove OpenPatch?")),
                  message: Text(L("Delivery stops and the pod is deactivated.")),
                  primaryButton: .destructive(Text(L("Remove")), action: model.removePump),
                  secondaryButton: .cancel())
        }
        .onAppear { model.refresh() }
    }

    private var statusSection: some View {
        Section(header: Text(L("Pod"))) {
            row(L("Status"), model.phaseText)
            row(L("Size"), model.state.podSize.displayName)
            row(L("Reservoir"), model.reservoirText)
            row(L("Battery"), model.batteryText)
            if let sync = model.state.lastSync {
                row(L("Last sync"), sync.formatted(date: .omitted, time: .shortened))
            }
            Button(L("Refresh")) { model.refresh() }.disabled(model.isBusy)
        }
    }

    /// The drive preset the pod reports: the volume per step comes from it, an unknown one blocks delivery.
    private var driveSection: some View {
        Section(header: Text(L("Drive"))) {
            row(L("Preset"), model.driveText)
            row(L("Preset id"), model.driveIDText)
            row(L("Volume per step"), model.driveStepText)
            row(L("Refill method"), model.fillMethodText)
            row(L("Link"), model.securityText)
        }
    }

    private var deliverySection: some View {
        Section(header: Text(L("Delivery"))) {
            switch model.state.phase {
            case .active:
                Button(L("Suspend delivery")) { model.suspendOrResume() }.disabled(model.isBusy)
            case .suspended:
                Button(L("Resume delivery")) { model.suspendOrResume() }.disabled(model.isBusy)
            default:
                Text(L("Not available in the current pod state.")).foregroundColor(.secondary)
            }
        }
    }

    private var podSection: some View {
        Section(header: Text(L("Pod handling"))) {
            if model.state.phase == .deactivated {
                Button(L("Refill and reuse pod")) { model.showRefill = true }
            } else {
                Button(L("Take pod off the dock")) { model.deactivatePod() }
                    .disabled(model.isBusy || model.state.phase == .unpaired)
            }
        }
    }

    /// Both pods with their own state, and the entry to the swap flow.
    private var pairSection: some View {
        Section(header: Text(L("Pods A / B"))) {
            if model.state.calibrationBlock != nil {
                Label(L("This pod's drive calibration is missing or unknown. Delivery is blocked."), systemImage: "exclamationmark.octagon.fill")
                    .foregroundColor(.red)
            }
            ForEach(model.pods, id: \.role) { pod in
                PodCard(record: pod, isActive: model.activeRole == pod.role)
            }
            Button(model.pods.count < 2 ? L("Pair spare pod") : L("Swap pod")) { model.showSwap = true }
                .disabled(model.isBusy || model.state.phase == .unpaired)
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack { Text(title); Spacer(); Text(value).foregroundColor(.secondary) }
            .accessibilityElement(children: .combine)
    }
}
