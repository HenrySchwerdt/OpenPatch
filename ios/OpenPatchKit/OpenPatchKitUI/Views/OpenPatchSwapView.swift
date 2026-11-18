import OpenPatchCore
import OpenPatchKit
import SwiftUI

/// Swap flow + spare pod management. One screen whose content follows the persisted swap phase, so it also
/// resumes correctly after an app restart in the middle of a swap.
struct OpenPatchSwapView: View {
    @ObservedObject var model: OpenPatchSwapViewModel

    var body: some View {
        NavigationView {
            Group {
                if !model.hasSpare { SparePairingView(model: model) } else { swapBody }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(L("Close"), action: model.onClose).disabled(model.phase != .idle && model.isBusy)
                }
            }
        }
        .navigationViewStyle(.stack)
        .onAppear { model.reload() }
    }

    private var swapBody: some View {
        StepContainer(systemImage: "arrow.triangle.2.circlepath", title: model.title, errorMessage: model.errorMessage,
                      primaryTitle: primaryTitle, primaryDisabled: false, isBusy: model.isBusy, primaryAction: primaryAction) {
            Text(model.instruction)
            podCards
            secondaryActions
        }
        .alert(isPresented: $model.confirmRemoval) {
            Alert(title: Text(L("Is the old pod removed?")),
                  message: Text(L("A pod that is off the cannula cannot deliver insulin. Only confirm if it is really removed from the cannula adapter.")),
                  primaryButton: .destructive(Text(L("Yes, it is removed")), action: model.confirmOldPodRemoved),
                  secondaryButton: .cancel())
        }
    }

    private var primaryTitle: String? {
        switch model.phase {
        case .idle: return L("Start swap")
        case .primeUncertain: return nil
        case .releasingOld, .oldPodUnconfirmed: return L("Try again")
        default: return L("Continue")
        }
    }

    private func primaryAction() { model.phase == .idle ? model.begin() : model.continueSwap() }

    @ViewBuilder private var secondaryActions: some View {
        switch model.phase {
        case .oldPodUnconfirmed, .releasingOld:
            Button(L("I removed the old pod from the cannula")) { model.confirmRemoval = true }.disabled(model.isBusy)
        case .awaitingDock:
            Button(L("Cannot use the new pod: take the old pod back")) { model.takeOldPodBack() }.disabled(model.isBusy)
        case .primeUncertain:
            Button(L("Prime again")) { model.retryPrime() }.buttonStyle(.borderedProminent).disabled(model.isBusy)
            Button(L("Continue without priming again")) { model.skipPrime() }.disabled(model.isBusy)
        case .idle:
            Button(L("Refresh spare pod")) { model.refreshSpare() }.disabled(model.isBusy)
        default:
            EmptyView()
        }
    }

    private var podCards: some View {
        VStack(spacing: 10) {
            ForEach(PodRole.allCases, id: \.self) { role in
                if let record = model.record(role) { PodCard(record: record, isActive: model.pair?.active == role) }
            }
        }
    }
}

/// Reservoir, battery, wear and dock state of ONE pod.
struct PodCard: View {
    let record: PodRecord
    let isActive: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(L("Pod %@", record.role.label)).bold()
                Spacer()
                Text(isActive ? L("Active") : L("Spare")).font(.caption.bold())
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(Capsule().fill(isActive ? Color.green.opacity(0.25) : Color.gray.opacity(0.25)))
            }
            Text(L("Insulin: %@", record.reservoirUnits.map { String(format: "%.0f U", $0) } ?? "-")).font(.callout)
            Text(L("Battery: %@", record.batteryFraction.map { "\(Int($0 * 100)) %" } ?? "-")).font(.callout)
            if isActive { Text(L("Worn: %@", wearText)).font(.callout) }
            Text(L("Dock: %@", record.isDocked.map { $0 ? L("docked") : L("not docked") } ?? "-")).font(.callout)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color(.secondarySystemBackground)))
        .accessibilityElement(children: .combine)
    }

    private var wearText: String {
        guard let seconds = record.wearSeconds else { return "-" }
        return String(format: "%.1f h", Double(seconds) / 3600)
    }
}

struct SparePairingView: View {
    @ObservedObject var model: OpenPatchSwapViewModel

    var body: some View {
        StepContainer(systemImage: "plus.circle", title: L("Pair the spare pod"), errorMessage: model.errorMessage) {
            Text(L("A second pod lets you swap without waiting: one pod delivers while the other is charged and refilled. Wake the spare pod with its button."))
            if model.bluetoothUnavailable {
                Label(L("Bluetooth is off or not allowed for this app."), systemImage: "bolt.horizontal.circle").foregroundColor(.red)
            }
            ForEach(model.discovered) { pod in
                Button { model.pairSpare(with: pod) } label: { Text(pod.name).bold() }.disabled(model.isBusy)
            }
            if model.allowSimulator {
                Button(L("Use simulated pod (development)")) { model.pairSpareSimulator() }.disabled(model.isBusy)
            }
            if model.isBusy { ProgressView(L("Pairing...")) }
        }
        .onAppear { model.startScan() }
        .onDisappear { model.stopScan() }
    }
}
