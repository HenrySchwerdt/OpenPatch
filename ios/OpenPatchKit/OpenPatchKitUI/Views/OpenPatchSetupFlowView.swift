import OpenPatchCore
import OpenPatchKit
import SwiftUI

struct OpenPatchSetupFlowView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        NavigationView {
            Group {
                switch model.step {
                case .size: PodSizeSelectionView(model: model)
                case .pairing: PairingView(model: model)
                case .fill: FillPodView(model: model)
                case .prime: PrimeView(model: model)
                case .attach: AttachView(model: model)
                case .done: SetupCompleteView(model: model)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if model.step != .done {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(L("Cancel")) { model.cancel() }
                    }
                }
            }
        }
        .navigationViewStyle(.stack)
    }
}

struct PodSizeSelectionView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        StepContainer(systemImage: "ruler", title: L("Choose your pod size"),
                      primaryTitle: L("Continue"), primaryAction: model.confirmSize) {
            Text(L("The pod sizes only differ in reservoir length. Pick the size printed on your pod."))
            Picker(L("Pod size"), selection: $model.podSize) {
                ForEach(PodSize.allCases) { size in
                    Text("\(size.rawValue) U").tag(size)
                }
            }
            .pickerStyle(.segmented)
            Text(L("Capacity: %.0f U (%.1f ml).", model.podSize.capacityUnits, model.podSize.capacityUnits / 100))
                .font(.footnote).foregroundColor(.secondary)
            Label(L("OpenPatch is an experimental test device and not a medical device. It is for bench tests only: water into a vial on a balance. Never wear it, never fill it with insulin or any other drug."),
                  systemImage: "exclamationmark.shield.fill")
                .font(.footnote).foregroundColor(.orange)
        }
    }
}

struct PairingView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        StepContainer(systemImage: "dot.radiowaves.left.and.right", title: L("Pair your pod"), errorMessage: model.errorMessage) {
            Text(L("Place the pod next to your phone and press its button: this wakes it and opens its 60 second pairing window. Nearby pods appear below."))
            if model.bluetoothUnavailable {
                Label(L("Bluetooth is off or not allowed for this app."), systemImage: "bolt.horizontal.circle")
                    .foregroundColor(.red)
            }
            if model.discovered.isEmpty && !model.bluetoothUnavailable {
                HStack { ProgressView(); Text(L("Searching for pods...")) }
            }
            ForEach(model.discovered) { pod in
                Button { model.pair(with: pod) } label: {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(pod.name).bold()
                            Text("\(pod.rssi) dBm").font(.caption).foregroundColor(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                    }
                    .padding(12)
                    .background(RoundedRectangle(cornerRadius: 10).fill(Color(.secondarySystemBackground)))
                }
                .disabled(model.isBusy)
                .buttonStyle(.plain)
            }
            if model.allowSimulator {
                Button(L("Use simulated pod (development)")) { model.pairSimulator() }
                    .disabled(model.isBusy)
            }
            if model.isBusy { ProgressView(L("Pairing...")) }
        }
        .onAppear { model.startScan() }
    }
}

struct SetupCompleteView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        StepContainer(systemImage: "checkmark.circle.fill", title: L("OpenPatch is delivering water"),
                      primaryTitle: L("Done"), primaryAction: model.finish) {
            Text(L("Basal delivery has started on the bench. Watch the balance and log the delivered mass."))
        }
    }
}
