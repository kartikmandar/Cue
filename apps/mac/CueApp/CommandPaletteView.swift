import SwiftUI

struct CommandPaletteView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        HStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    commandInput
                    SafetyBlockView(session: appState.currentSession, phase: appState.phase)
                    WorkflowPlanView(
                        plan: appState.currentSession?.workflowPlan,
                        currentStepID: appState.currentSession?.currentStepID,
                        verifiedSteps: appState.currentSession?.verifiedSteps ?? []
                    )
                    ConfirmationView(
                        prompt: appState.currentSession?.confirmationPrompt,
                        approvalTier: appState.currentSession?.policyDecision?.approvalTier
                            ?? appState.currentSession?.workflowPlan?.approvalTier,
                        requiresReviewerApproval: appState.currentSession?.policyDecision?.requiresReviewerApproval
                            ?? false,
                        approve: { Task { await appState.approveWorkflow() } },
                        requestReviewer: { Task { await appState.requestReviewerApproval() } },
                        cancel: { Task { await appState.cancelWorkflow() } }
                    )
                    VerificationView(
                        result: appState.currentSession?.lastVerification,
                        phase: appState.phase,
                        reobserve: { Task { await appState.previewCommand() } },
                        revisePlan: { Task { await appState.previewCommand() } },
                        cancel: { Task { await appState.cancelWorkflow() } }
                    )
                }
                .padding(24)
            }

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    trustRail
                    FocusStatusView(focus: appState.focusStatus)
                    PrivacyStatusView(status: appState.onboardingStatus, privacyMode: appState.privacyMode)
                    TimingView(timing: appState.currentSession?.timing)
                    AuditTrailView(
                        events: appState.currentSession?.auditEvents ?? [],
                        summary: appState.auditSummary
                    )
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(width: 330)
            .background(Color(nsColor: .underPageBackgroundColor))
        }
        .frame(minWidth: 940, minHeight: 680)
        .task {
            appState.refreshLocalStatus()
            if !ProcessInfo.processInfo.isCueRunningXCTest {
                await appState.refreshBackendHealth()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Cue")
                    .font(.system(size: 34, weight: .semibold, design: .rounded))
                Text("Plan, ask, act, verify, narrate")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            statusPill
        }
        .accessibilityElement(children: .combine)
    }

    private var commandInput: some View {
        VStack(alignment: .leading, spacing: 12) {
            InputModePicker(selection: $appState.inputMode, voiceEnabled: appState.speechEnabled)

            TextField("Ask Cue what to do next", text: $appState.commandText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .font(.title3)
                .lineLimit(3...6)
                .accessibilityLabel("Cue request")

            HStack(spacing: 10) {
                Button {
                    Task { await appState.previewCommand() }
                } label: {
                    Label("Preview", systemImage: "text.magnifyingglass")
                }
                .keyboardShortcut(.return, modifiers: [.command])
                .buttonStyle(.borderedProminent)
                .disabled(appState.commandText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || appState.phase.isBusy)

                Button {
                    Task { await appState.approveWorkflow() }
                } label: {
                    Label("Approve", systemImage: "checkmark.seal")
                }
                .disabled(!appState.pendingApproval || appState.phase.isBusy)

                Button {
                    Task { await appState.executeNextStep() }
                } label: {
                    Label("Do Next Step", systemImage: "arrow.right.circle")
                }
                .disabled(appState.currentSession == nil || appState.pendingApproval || appState.phase.isTerminal || appState.phase.isBusy)

                Button(role: .cancel) {
                    Task { await appState.cancelWorkflow() }
                } label: {
                    Label("Cancel", systemImage: "xmark.circle")
                }
                .disabled(appState.currentSession == nil)

                Spacer()

                Toggle("Speech", isOn: $appState.speechEnabled)
                    .toggleStyle(.switch)
                    .accessibilityLabel("Speech narration")
            }

            if let lastErrorMessage = appState.lastErrorMessage {
                Label(lastErrorMessage, systemImage: "exclamationmark.triangle")
                    .font(.callout)
                    .foregroundStyle(.red)
                    .accessibilityLabel("Cue error: \(lastErrorMessage)")
            }
        }
    }

    private var trustRail: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Trust Rail")
                .font(.headline)
            TrustRailRow(title: "Phase", value: appState.phase.displayName, systemImage: appState.phase.iconName)
            TrustRailRow(
                title: "Policy",
                value: appState.currentSession?.policyDecision?.allowed == false ? "Blocked" : "Allowed or pending",
                systemImage: appState.currentSession?.policyDecision?.allowed == false ? "hand.raised" : "checkmark.shield"
            )
            TrustRailRow(
                title: "Verification",
                value: appState.currentSession?.lastVerification?.status.capitalized ?? "Not started",
                systemImage: "checklist.checked"
            )
            TrustRailRow(
                title: "Hotkey",
                value: "Shift Command Space",
                systemImage: "keyboard"
            )
        }
    }

    private var statusPill: some View {
        Label(appState.phase.displayName, systemImage: appState.phase.iconName)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(Color.accentColor.opacity(0.14), in: Capsule())
            .accessibilityLabel("Cue status \(appState.phase.displayName)")
    }
}

private struct TrustRailRow: View {
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

private extension CuePhase {
    var displayName: String {
        switch self {
        case .idle:
            "Ready"
        case .previewReady:
            "Preview Ready"
        case .awaitingWorkflowApproval:
            "Awaiting Approval"
        case .awaitingStepApproval:
            "Step Approval"
        case .awaitingReviewerApproval:
            "Reviewer Approval"
        case .executingStep, .acting:
            "Executing"
        case .verificationFailed:
            "Verification Failed"
        case .completed:
            "Completed"
        case .blocked:
            "Blocked"
        case .cancelled:
            "Cancelled"
        case .error:
            "Error"
        case .thinking:
            "Thinking"
        case .verifying:
            "Verifying"
        case .paused:
            "Paused"
        case .unknown:
            "Unknown"
        }
    }

    var iconName: String {
        switch self {
        case .idle, .previewReady:
            "sparkle.magnifyingglass"
        case .awaitingWorkflowApproval, .awaitingStepApproval, .awaitingReviewerApproval:
            "person.crop.circle.badge.checkmark"
        case .executingStep, .acting:
            "play.circle"
        case .verificationFailed, .blocked, .error:
            "exclamationmark.octagon"
        case .completed:
            "checkmark.circle"
        case .cancelled, .paused:
            "pause.circle"
        case .thinking:
            "brain"
        case .verifying:
            "checklist"
        case .unknown:
            "questionmark.circle"
        }
    }

    var isBusy: Bool {
        self == .thinking || self == .acting || self == .executingStep || self == .verifying
    }

    var isTerminal: Bool {
        self == .completed || self == .blocked || self == .cancelled
    }
}

private extension ProcessInfo {
    var isCueRunningXCTest: Bool {
        environment["XCTestConfigurationFilePath"] != nil
    }
}
