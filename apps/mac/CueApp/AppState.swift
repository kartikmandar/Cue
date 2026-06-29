import AppKit
import ApplicationServices
import Combine
import CoreGraphics
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var phase: CuePhase = .idle
    @Published var commandText = ""
    @Published var inputMode: CueInputMode = .voice
    @Published var conversationID: String?
    @Published var conversationMessages: [CueConversationMessage] = [CueConversationMessage.welcome()]
    @Published var suggestedReplies: [String] = []
    @Published var detailsInspectorVisible = false
    @Published var backendHealth: BackendHealth = .unknown
    @Published var currentSession: CueSessionState?
    @Published var lastResponse: CueWorkflowPreviewResponse?
    @Published var speechEnabled = true
    @Published var privacyMode = "strict"
    @Published var pendingApproval = false
    @Published var focusStatus: CueFocusStatus?
    @Published var auditSummary: [String] = []
    @Published var onboardingStatus = CueOnboardingStatus.defaults
    @Published var lastErrorMessage: String?

    private let backendClient: any BackendClientProtocol
    private let permissionChecker: PermissionChecker
    private let speechController: SpeechController
    let voiceInputController: VoiceInputController

    init(
        backendClient: any BackendClientProtocol = BackendClient(),
        permissionChecker: PermissionChecker = PermissionChecker(),
        speechController: SpeechController = SpeechController(),
        voiceInputController: VoiceInputController = VoiceInputController()
    ) {
        self.backendClient = backendClient
        self.permissionChecker = permissionChecker
        self.speechController = speechController
        self.voiceInputController = voiceInputController
        refreshLocalStatus()
    }

    func refreshLocalStatus() {
        let environment = ProcessInfo.processInfo.environment
        let status = permissionChecker.snapshot()
        privacyMode = status.strictPrivacyMode ? "strict" : environment["CUE_PRIVACY_MODE", default: "standard"]
        speechEnabled = environment["CUE_SPEAK"].map { $0 != "false" } ?? true
        onboardingStatus = status
    }

    func refreshBackendHealth() async {
        do {
            let response = try await backendClient.health()
            backendHealth = response.status == "ok" ? .healthy : .unavailable
            lastErrorMessage = nil
        } catch {
            backendHealth = .unavailable
            lastErrorMessage = error.localizedDescription
        }
    }

    func previewCommand() async {
        let command = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else {
            lastErrorMessage = "Enter a Cue command first."
            return
        }
        phase = .thinking
        do {
            let response = try await backendClient.preview(command: command)
            lastResponse = response
            apply(response.session)
            speak(response.session.narration?.speakableText ?? response.session.workflowPlan?.narration)
            lastErrorMessage = nil
        } catch {
            phase = .error
            lastErrorMessage = error.localizedDescription
        }
    }

    func sendChatCommand(_ rawCommand: String? = nil) async {
        let command = (rawCommand ?? commandText).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else {
            lastErrorMessage = "Ask Cue something first."
            return
        }

        conversationMessages.append(
            CueConversationMessage(role: .user, text: command)
        )
        commandText = ""
        phase = .thinking

        do {
            let response = try await backendClient.chat(command: command, conversationID: conversationID)
            conversationID = response.conversationID
            suggestedReplies = response.suggestedReplies
            conversationMessages.append(
                CueConversationMessage(
                    role: .assistant,
                    text: response.assistantMessage,
                    mode: response.mode,
                    session: response.session,
                    suggestedReplies: response.suggestedReplies
                )
            )
            if let session = response.session {
                apply(session)
            } else {
                phase = .idle
            }
            speak(response.assistantMessage)
            lastErrorMessage = nil
        } catch {
            phase = .error
            suggestedReplies = []
            lastErrorMessage = error.localizedDescription
            conversationMessages.append(
                CueConversationMessage(
                    role: .assistant,
                    text: "I could not reach the Cue backend. \(error.localizedDescription)",
                    mode: .blocked
                )
            )
        }
    }

    func approveWorkflow() async {
        guard let sessionID = currentSession?.sessionID else { return }
        _ = await updateSession {
            try await backendClient.approve(sessionID: sessionID)
        }
    }

    func executeNextStep() async {
        guard let sessionID = currentSession?.sessionID else { return }
        phase = .acting
        let session = await updateSession {
            try await backendClient.next(sessionID: sessionID)
        }
        speak(session?.lastVerification?.reason ?? session?.narration?.speakableText)
    }

    func cancelWorkflow() async {
        guard let sessionID = currentSession?.sessionID else { return }
        speechController.stop()
        _ = await updateSession {
            try await backendClient.cancel(sessionID: sessionID)
        }
    }

    func requestReviewerApproval() async {
        guard let sessionID = currentSession?.sessionID else { return }
        _ = await updateSession {
            try await backendClient.requestReview(sessionID: sessionID)
        }
    }

    func confirmReviewerApproval(approved: Bool) async {
        guard let sessionID = currentSession?.sessionID else { return }
        _ = await updateSession {
            try await backendClient.confirmReviewer(sessionID: sessionID, approved: approved)
        }
    }

    func pauseCue() {
        pendingApproval = false
        phase = .paused
    }

    func apply(_ session: CueSessionState) {
        currentSession = session
        phase = session.phase
        pendingApproval = session.phase == .awaitingWorkflowApproval
            || session.phase == .awaitingStepApproval
            || session.phase == .awaitingReviewerApproval
        focusStatus = session.focusStatus
        auditSummary = session.auditSummary
    }

    private func updateSession(_ operation: () async throws -> CueSessionState) async -> CueSessionState? {
        do {
            let session = try await operation()
            apply(session)
            lastErrorMessage = nil
            return session
        } catch {
            phase = .error
            lastErrorMessage = error.localizedDescription
            return nil
        }
    }

    private func speak(_ text: String?) {
        speechController.speak(text, enabled: speechEnabled)
    }
}

enum CueInputMode: String, CaseIterable, Identifiable {
    case text
    case voice

    var id: String { rawValue }
}

enum BackendHealth: String {
    case unknown
    case healthy
    case unavailable
}

enum LocalStatus: String {
    case ready
    case missing
    case needsPermission

    var label: String {
        switch self {
        case .ready:
            "Ready"
        case .missing:
            "Missing"
        case .needsPermission:
            "Needs Permission"
        }
    }
}

struct CueOnboardingStatus: Equatable {
    let cuaStatus: LocalStatus
    let accessibilityPermission: LocalStatus
    let screenRecordingPermission: LocalStatus
    let microphonePermission: LocalStatus
    let speechRecognitionPermission: LocalStatus
    let cerebrasAPIKeyStatus: LocalStatus
    let strictPrivacyMode: Bool
    let auditRedactionEnabled: Bool
    let terminalWriteDisabled: Bool
    let reviewerModeEnabled: Bool

    static let defaults = CueOnboardingStatus(
        cuaStatus: .missing,
        accessibilityPermission: .needsPermission,
        screenRecordingPermission: .needsPermission,
        microphonePermission: .needsPermission,
        speechRecognitionPermission: .needsPermission,
        cerebrasAPIKeyStatus: .missing,
        strictPrivacyMode: true,
        auditRedactionEnabled: true,
        terminalWriteDisabled: true,
        reviewerModeEnabled: false
    )
}

private extension Optional where Wrapped == String {
    var isNilOrEmpty: Bool {
        switch self {
        case .none:
            true
        case .some(let value):
            value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }
}
