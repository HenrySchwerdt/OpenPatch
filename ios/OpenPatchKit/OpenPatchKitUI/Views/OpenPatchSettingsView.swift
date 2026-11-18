import OpenPatchCore
import SwiftUI

struct OpenPatchSettingsView: View {
    @ObservedObject var model: OpenPatchSettingsViewModel

    var body: some View {
        List {
            if model.state.deliveryUncertainSince != nil {
                Section {
                    Label(L("Delivery status is uncertain. Check the pod and your glucose."), systemImage: "exclamationmark.circle.fill")
                        .foregroundColor(.red)
                }
            }
            statusSection
            deliverySection
            podSection
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
        .sheet(isPresented: $model.showRefill) {
            OpenPatchSetupFlowView(model: model.makeRefillModel())
        }
        .alert(isPresented: $model.confirmRemoval) {
            Alert(title: Text(L("Remove OpenPatch?")),
                  message: Text(L("Insulin delivery stops and the pod is deactivated.")),
                  primaryButton: .destructive(Text(L("Remove")), action: model.removePump),
                  secondaryButton: .cancel())
        }
        .onAppear { model.refresh() }
    }

    private var statusSection: some View {
        Section(header: Text(L("Pod"))) {
            row(L("Status"), model.phaseText)
            row(L("Size"), model.state.podSize.displayName)
            row(L("Insulin"), model.reservoirText)
            row(L("Battery"), model.batteryText)
            if let sync = model.state.lastSync {
                row(L("Last sync"), sync.formatted(date: .omitted, time: .shortened))
            }
            Button(L("Refresh")) { model.refresh() }.disabled(model.isBusy)
        }
    }

    private var deliverySection: some View {
        Section(header: Text(L("Insulin delivery"))) {
            switch model.state.phase {
            case .active:
                Button(L("Suspend insulin delivery")) { model.suspendOrResume() }.disabled(model.isBusy)
            case .suspended:
                Button(L("Resume insulin delivery")) { model.suspendOrResume() }.disabled(model.isBusy)
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
                Button(L("Remove pod from body")) { model.deactivatePod() }
                    .disabled(model.isBusy || model.state.phase == .unpaired)
            }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack { Text(title); Spacer(); Text(value).foregroundColor(.secondary) }
            .accessibilityElement(children: .combine)
    }
}
