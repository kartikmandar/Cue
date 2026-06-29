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
    @Published var speechPreferences: SpeechPreferences
    @Published var speechVoiceOptions: [SpeechVoiceOption]
    @Published var privacyMode = "strict"
    @Published var yoloMode = false
    @Published var modelProvider: CueModelProvider = .cerebras
    @Published var activeModel = "gemma-4-31b"
    @Published var pendingApproval = false
    @Published var focusStatus: CueFocusStatus?
    @Published var auditSummary: [String] = []
    @Published var onboardingStatus = CueOnboardingStatus.defaults
    @Published var lastErrorMessage: String?

    private let backendClient: any BackendClientProtocol
    private let permissionChecker: PermissionChecker
    private let speechController: SpeechController
    private let speechPreferenceStore: SpeechPreferenceStore
    private var lastAutoSubmittedVoiceCommand: String?
    let voiceInputController: VoiceInputController

    init(
        backendClient: any BackendClientProtocol = BackendClient(),
        permissionChecker: PermissionChecker = PermissionChecker(),
        speechController: SpeechController = SpeechController(),
        speechPreferenceStore: SpeechPreferenceStore = SpeechPreferenceStore(),
        voiceInputController: VoiceInputController = VoiceInputController()
    ) {
        self.backendClient = backendClient
        self.permissionChecker = permissionChecker
        self.speechController = speechController
        self.speechPreferenceStore = speechPreferenceStore
        self.speechPreferences = speechPreferenceStore.load()
        self.speechVoiceOptions = SpeechController.availableVoices()
        self.voiceInputController = voiceInputController
        refreshLocalStatus()
    }

    func refreshLocalStatus() {
        let environment = ProcessInfo.processInfo.environment
        let status = permissionChecker.snapshot()
        privacyMode = status.strictPrivacyMode ? "strict" : environment["CUE_PRIVACY_MODE", default: "standard"]
        yoloMode = environment["CUE_YOLO_MODE"].map { $0 == "true" } ?? yoloMode
        if let provider = environment["CUE_MODEL_PROVIDER"].flatMap(CueModelProvider.init(rawValue:)) {
            modelProvider = provider
        }
        speechEnabled = environment["CUE_SPEAK"].map { $0 != "false" } ?? true
        onboardingStatus = status
        refreshPendingApproval()
    }

    func refreshBackendHealth() async {
        do {
            let response = try await backendClient.health()
            backendHealth = response.status == "ok" ? .healthy : .unavailable
            if let backendYoloMode = response.yoloMode {
                yoloMode = backendYoloMode
                refreshPendingApproval()
            }
            if let backendProvider = response.modelProvider {
                modelProvider = backendProvider
            }
            if let backendModel = response.model {
                activeModel = backendModel
            }
            lastErrorMessage = nil
        } catch {
            backendHealth = .unavailable
            lastErrorMessage = error.localizedDescription
        }
    }

    func setYoloMode(_ enabled: Bool) async {
        let previous = yoloMode
        yoloMode = enabled
        refreshPendingApproval()
        do {
            let response = try await backendClient.setYoloMode(enabled)
            apply(response)
            lastErrorMessage = nil
        } catch {
            yoloMode = previous
            refreshPendingApproval()
            phase = .error
            lastErrorMessage = error.localizedDescription
        }
    }

    func setModelProvider(_ provider: CueModelProvider) async {
        let previousProvider = modelProvider
        let previousModel = activeModel
        modelProvider = provider
        activeModel = provider.defaultModel
        do {
            let response = try await backendClient.setMode(
                yoloMode: nil,
                modelProvider: provider
            )
            apply(response)
            lastErrorMessage = nil
        } catch {
            modelProvider = previousProvider
            activeModel = previousModel
            phase = .error
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

    func prepareForVoiceCommandCapture() {
        lastAutoSubmittedVoiceCommand = nil
    }

    func startGlobalVoiceCommandCapture() {
        guard !phase.isBusy else { return }
        inputMode = .voice
        prepareForVoiceCommandCapture()
        voiceInputController.clearTranscript()
        commandText = ""
        voiceInputController.startListening()
    }

    func sendVoiceCommandIfTranscriptReady(voiceState: VoiceInputState) async {
        guard inputMode == .voice else { return }
        guard voiceState == .transcribing else { return }
        guard !phase.isBusy else { return }
        let command = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else { return }
        guard command != lastAutoSubmittedVoiceCommand else { return }

        lastAutoSubmittedVoiceCommand = command
        await sendChatCommand(command)
    }

    func approveWorkflow() async {
        guard let sessionID = currentSession?.sessionID else { return }
        let approvedSession = await updateSession {
            try await backendClient.approve(sessionID: sessionID)
        }
        if approvedSession?.phase == .awaitingStepApproval {
            await executeNextStep()
        } else {
            speak(approvedSession?.narration?.speakableText)
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

    func setSpeechVoiceIdentifier(_ voiceIdentifier: String?) {
        updateSpeechPreferences(
            SpeechPreferences(
                voiceIdentifier: voiceIdentifier,
                rate: speechPreferences.rate,
                pitchMultiplier: speechPreferences.pitchMultiplier
            )
        )
    }

    func setSpeechRate(_ rate: Float) {
        updateSpeechPreferences(
            SpeechPreferences(
                voiceIdentifier: speechPreferences.voiceIdentifier,
                rate: rate,
                pitchMultiplier: speechPreferences.pitchMultiplier
            )
        )
    }

    func setSpeechPitchMultiplier(_ pitchMultiplier: Float) {
        updateSpeechPreferences(
            SpeechPreferences(
                voiceIdentifier: speechPreferences.voiceIdentifier,
                rate: speechPreferences.rate,
                pitchMultiplier: pitchMultiplier
            )
        )
    }

    func resetSpeechPreferences() {
        updateSpeechPreferences(.defaults)
    }

    func previewSpeechVoice() {
        speechController.speak(
            "This is Cue using the selected voice.",
            enabled: true,
            preferences: speechPreferences
        )
    }

    func apply(_ session: CueSessionState) {
        currentSession = session
        phase = session.phase
        pendingApproval = approvalIsPending(for: session.phase)
        focusStatus = session.focusStatus
        auditSummary = session.auditSummary
    }

    func apply(_ mode: CueModeResponse) {
        yoloMode = mode.yoloMode
        modelProvider = mode.modelProvider
        activeModel = mode.model
        refreshPendingApproval()
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
        speechController.speak(text, enabled: speechEnabled, preferences: speechPreferences)
    }

    private func updateSpeechPreferences(_ preferences: SpeechPreferences) {
        speechPreferences = preferences
        speechPreferenceStore.save(preferences)
    }

    private func refreshPendingApproval() {
        pendingApproval = currentSession.map { approvalIsPending(for: $0.phase) } ?? false
    }

    private func approvalIsPending(for phase: CuePhase) -> Bool {
        !yoloMode
            && (
                phase == .awaitingWorkflowApproval
                    || phase == .awaitingStepApproval
                    || phase == .awaitingReviewerApproval
            )
    }
}

enum CueInputMode: String, CaseIterable, Identifiable {
    case text
    case voice

    var id: String { rawValue }
}

enum BackendHealth: String, Equatable {
    case unknown
    case healthy
    case unavailable
}

extension CueModelProvider {
    var defaultModel: String {
        switch self {
        case .cerebras:
            "gemma-4-31b"
        case .openrouter:
            "google/gemma-4-31b-it:free"
        }
    }
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
