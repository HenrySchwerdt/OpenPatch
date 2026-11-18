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
            Text(L("Capacity: %.0f U of U100 insulin.", model.podSize.capacityUnits))
                .font(.footnote).foregroundColor(.secondary)
            Label(L("OpenPatch is an experimental DIY device and not an approved medical device. Use it only if you understand the risks, and always keep a backup way to deliver insulin."),
                  systemImage: "exclamationmark.shield.fill")
                .font(.footnote).foregroundColor(.orange)
        }
    }
}

struct PairingView: View {
    @ObservedObject var model: OpenPatchSetupViewModel

    var body: some View {
        StepContainer(systemImage: "dot.radiowaves.left.and.right", title: L("Pair your pod"), errorMessage: model.errorMessage) {
            Text(L("Place the pod next to your phone and wake it with the button. Nearby pods appear below."))
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
        StepContainer(systemImage: "checkmark.circle.fill", title: L("OpenPatch is delivering insulin"),
                      primaryTitle: L("Done"), primaryAction: model.finish) {
            Text(L("Basal delivery has started. Check your glucose regularly during the first hours."))
        }
    }
}
