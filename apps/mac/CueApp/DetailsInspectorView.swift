import SwiftUI

struct DetailsInspectorView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                trustRail
                FocusStatusView(focus: appState.focusStatus)
                PrivacyStatusView(status: appState.onboardingStatus, privacyMode: appState.privacyMode)
                TimingView(timing: appState.currentSession?.timing)
                AuditTrailView(
                    events: appState.currentSession?.auditEvents ?? [],
                    summary: appState.auditSummary
                )
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color(nsColor: .underPageBackgroundColor))
        .accessibilityElement(children: .contain)
    }

    private var header: some View {
        HStack {
            Text("Details")
                .font(.headline)
            Spacer()
            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    appState.detailsInspectorVisible = false
                }
            } label: {
                Label("Close Details", systemImage: "xmark.circle")
                    .labelStyle(.iconOnly)
            }
            .accessibilityLabel("Close details")
        }
    }

    private var trustRail: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Trust Rail")
                .font(.headline)
            DetailsRailRow(title: "Phase", value: appState.phase.displayName, systemImage: appState.phase.iconName)
            DetailsRailRow(
                title: "Policy",
                value: appState.currentSession?.policyDecision?.allowed == false ? "Blocked" : "Allowed or pending",
                systemImage: appState.currentSession?.policyDecision?.allowed == false ? "hand.raised" : "checkmark.shield"
            )
            DetailsRailRow(
                title: "Verification",
                value: appState.currentSession?.lastVerification?.status.capitalized ?? "Not started",
                systemImage: "checklist.checked"
            )
            DetailsRailRow(
                title: "Hotkey",
                value: "Shift Command Space",
                systemImage: "keyboard"
            )
        }
        .accessibilityElement(children: .combine)
    }
}

private struct DetailsRailRow: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage)
                .frame(width: 18)
                .foregroundStyle(Color.accentColor)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.callout)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
