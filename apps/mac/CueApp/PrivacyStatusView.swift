import SwiftUI

struct PrivacyStatusView: View {
    let status: CueOnboardingStatus
    let privacyMode: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Privacy", systemImage: "lock.shield")
                .font(.headline)
            PrivacyLine(title: "Mode", value: privacyMode.capitalized, isReady: status.strictPrivacyMode)
            PrivacyLine(title: "Screenshots", value: "Persistence Off", isReady: true)
            PrivacyLine(title: "Audit", value: status.auditRedactionEnabled ? "Redacted" : "Raw", isReady: status.auditRedactionEnabled)
            PrivacyLine(title: "Terminal Write", value: status.terminalWriteDisabled ? "Disabled" : "Enabled", isReady: status.terminalWriteDisabled)
            PrivacyLine(title: "Cua Driver", value: status.cuaStatus.label, isReady: status.cuaStatus == .ready)
            PrivacyLine(title: "Accessibility", value: status.accessibilityPermission.label, isReady: status.accessibilityPermission == .ready)
            PrivacyLine(title: "Screen Recording", value: status.screenRecordingPermission.label, isReady: status.screenRecordingPermission == .ready)
        }
        .accessibilityElement(children: .contain)
    }
}

private struct PrivacyLine: View {
    let title: String
    let value: String
    let isReady: Bool

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Label(title, systemImage: isReady ? "checkmark.circle" : "exclamationmark.circle")
                .font(.caption.weight(.semibold))
                .foregroundStyle(isReady ? .green : .orange)
            Spacer()
            Text(value)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
