import SwiftUI

/// Common layout for a setup step: icon, title, explanatory content, error line, primary action.
struct StepContainer<Content: View>: View {
    let systemImage: String
    let title: String
    var errorMessage: String?
    var primaryTitle: String?
    var primaryDisabled = false
    var isBusy = false
    var primaryAction: () -> Void = {}
    @ViewBuilder var content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Image(systemName: systemImage)
                    .font(.system(size: 44, weight: .semibold))
                    .foregroundColor(.accentColor)
                    .accessibilityHidden(true)
                Text(title)
                    .font(.title2.weight(.bold))
                    .accessibilityAddTraits(.isHeader)
                content()
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                        .font(.callout)
                }
                if let primaryTitle {
                    Button(action: primaryAction) {
                        HStack {
                            if isBusy { ProgressView() }
                            Text(primaryTitle).bold()
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(primaryDisabled || isBusy)
                }
            }
            .padding(20)
        }
    }
}

struct NumberedInstruction: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.footnote.weight(.bold))
                .foregroundColor(.white)
                .frame(width: 24, height: 24)
                .background(Circle().fill(Color.accentColor))
                .accessibilityHidden(true)
            Text(text).fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(L("Step %d: %@", number, text))
    }
}
