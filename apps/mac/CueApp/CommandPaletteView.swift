import SwiftUI

struct CommandPaletteView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        HStack(spacing: 0) {
            ConversationView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)

            if appState.detailsInspectorVisible {
                Divider()
                DetailsInspectorView()
                    .frame(width: 330)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
            }
        }
        .frame(minWidth: 760, minHeight: 640)
        .animation(.easeInOut(duration: 0.18), value: appState.detailsInspectorVisible)
        .task {
            appState.refreshLocalStatus()
            if ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] == nil {
                await appState.refreshBackendHealth()
            }
        }
    }
}

extension CuePhase {
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
