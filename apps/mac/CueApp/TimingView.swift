import SwiftUI

struct TimingView: View {
    let timing: CueTiming?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Timing", systemImage: "timer")
                .font(.headline)
            TimingLine(title: "Provider", value: timing?.provider?.displayName ?? "Pending")
            TimingLine(title: "Model", value: timing?.model ?? "Pending")
            TimingLine(title: "Latency", value: timing?.latencyMS.msLabel ?? "Pending")
            TimingLine(title: "Tokens", value: timing?.tokenUsage.map(String.init) ?? "Pending")
            TimingLine(title: "Action Loop", value: timing?.actionLoopMS.msLabel ?? "Pending")
            TimingLine(title: "Verification", value: timing?.verificationMS.msLabel ?? "Pending")
            TimingLine(title: "Backend", value: timing?.backendMS.msLabel ?? "Pending")
        }
        .accessibilityElement(children: .contain)
    }
}

private struct TimingLine: View {
    let title: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.caption.monospacedDigit())
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }
}

private extension Optional where Wrapped == Int {
    var msLabel: String? {
        map { "\($0) ms" }
    }
}
