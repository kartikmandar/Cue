import AVFoundation
import XCTest
@testable import CueApp

final class AppStateConversationTests: XCTestCase {
    @MainActor
    func testAppStateDefaultsToVoiceFirstConversation() {
        let appState = AppState(backendClient: StubBackendClient())

        XCTAssertEqual(appState.inputMode, .voice)
        XCTAssertFalse(appState.detailsInspectorVisible)
        XCTAssertEqual(appState.conversationMessages.first?.role, .assistant)
    }

    @MainActor
    func testSendChatCommandAppendsConversationAndAppliesActionSession() async {
        let session = CueSessionState(
            sessionID: "session-123",
            phase: .awaitingWorkflowApproval,
            policyDecision: CuePolicyDecision(
                allowed: true,
                approvalTier: "confirm_each_action",
                reason: "Allowed for test.",
                requiresReviewerApproval: false,
                redactionApplied: false
            ),
            confirmationPrompt: "Approve opening TextEdit?"
        )
        let client = StubBackendClient(
            chatResponse: CueChatResponse(
                conversationID: "conversation-123",
                assistantMessage: "I can do that. Approve opening TextEdit?",
                mode: .actionPreview,
                session: session,
                suggestedReplies: ["Approve", "Cancel"]
            )
        )
        let appState = AppState(backendClient: client)
        let initialMessageCount = appState.conversationMessages.count

        appState.commandText = "Open TextEdit"
        await appState.sendChatCommand()

        XCTAssertEqual(client.chatRequests, [
            StubBackendClient.ChatRequest(command: "Open TextEdit", conversationID: nil)
        ])
        XCTAssertEqual(appState.commandText, "")
        XCTAssertEqual(appState.conversationID, "conversation-123")
        XCTAssertEqual(appState.currentSession?.sessionID, "session-123")
        XCTAssertTrue(appState.pendingApproval)
        XCTAssertEqual(appState.suggestedReplies, ["Approve", "Cancel"])
        XCTAssertEqual(appState.conversationMessages.count, initialMessageCount + 2)
        XCTAssertEqual(appState.conversationMessages.suffix(2).map(\.role), [.user, .assistant])
        XCTAssertEqual(appState.conversationMessages.last?.mode, .actionPreview)
        XCTAssertEqual(appState.conversationMessages.last?.session?.sessionID, "session-123")
    }

    @MainActor
    func testVoiceTranscriptAutoSubmitWaitsForTranscribingState() async {
        let client = StubBackendClient()
        let appState = AppState(backendClient: client)
        appState.commandText = "Open Notes"

        await appState.sendVoiceCommandIfTranscriptReady(voiceState: .listening)
        XCTAssertEqual(client.chatRequests, [])

        await appState.sendVoiceCommandIfTranscriptReady(voiceState: .transcribing)

        XCTAssertEqual(client.chatRequests, [
            StubBackendClient.ChatRequest(command: "Open Notes", conversationID: nil)
        ])
        XCTAssertEqual(appState.commandText, "")
    }

    @MainActor
    func testVoiceTranscriptAutoSubmitDoesNotRepeatWithinSameCapture() async {
        let client = StubBackendClient()
        let appState = AppState(backendClient: client)
        appState.prepareForVoiceCommandCapture()
        appState.commandText = "Open Notes"

        await appState.sendVoiceCommandIfTranscriptReady(voiceState: .transcribing)
        appState.commandText = "Open Notes"
        await appState.sendVoiceCommandIfTranscriptReady(voiceState: .transcribing)

        XCTAssertEqual(client.chatRequests, [
            StubBackendClient.ChatRequest(command: "Open Notes", conversationID: nil)
        ])

        appState.prepareForVoiceCommandCapture()
        appState.commandText = "Open Notes"
        await appState.sendVoiceCommandIfTranscriptReady(voiceState: .transcribing)

        XCTAssertEqual(client.chatRequests.count, 2)
    }

    @MainActor
    func testGlobalListenNowClearsStaleTextAndStartsVoiceCapture() async {
        let permissionRequester = DeferredAppStateVoicePermissionRequester()
        let voiceInputController = VoiceInputController(
            speechRecognizer: nil,
            permissionRequester: permissionRequester
        )
        let appState = AppState(voiceInputController: voiceInputController)
        appState.inputMode = .text
        appState.commandText = "stale command"

        appState.startGlobalVoiceCommandCapture()

        XCTAssertEqual(appState.inputMode, .voice)
        XCTAssertEqual(appState.commandText, "")
        XCTAssertTrue(voiceInputController.isRecordingSessionActive)

        permissionRequester.resolve(granted: false)
    }

    @MainActor
    func testGlobalListenNowDoesNotStartWhileCommandIsBusy() async {
        let voiceInputController = VoiceInputController(
            speechRecognizer: nil,
            permissionRequester: DeferredAppStateVoicePermissionRequester()
        )
        let appState = AppState(voiceInputController: voiceInputController)
        appState.phase = .thinking
        appState.inputMode = .text
        appState.commandText = "keep me"

        appState.startGlobalVoiceCommandCapture()

        XCTAssertEqual(appState.inputMode, .text)
        XCTAssertEqual(appState.commandText, "keep me")
        XCTAssertFalse(voiceInputController.isRecordingSessionActive)
    }

    @MainActor
    func testApproveWorkflowRunsFirstApprovedStep() async {
        let client = StubBackendClient(
            approveResponse: CueSessionState(
                sessionID: "session-123",
                phase: .awaitingStepApproval
            ),
            nextResponse: CueSessionState(
                sessionID: "session-123",
                phase: .completed,
                lastVerification: CueVerificationResult(
                    status: "passed",
                    reason: "Notes is active.",
                    expected: "Notes is active.",
                    actual: "Notes is active.",
                    nextRecommendation: "Continue."
                )
            )
        )
        let appState = AppState(backendClient: client)
        appState.currentSession = CueSessionState(
            sessionID: "session-123",
            phase: .awaitingWorkflowApproval
        )

        await appState.approveWorkflow()

        XCTAssertEqual(client.approveRequests, ["session-123"])
        XCTAssertEqual(client.nextRequests, ["session-123"])
        XCTAssertEqual(appState.phase, .completed)
        XCTAssertFalse(appState.pendingApproval)
    }

    @MainActor
    func testYoloModeToggleUpdatesBackendAndClearsPendingApproval() async {
        let client = StubBackendClient(
            modeResponse: CueModeResponse(
                yoloMode: true,
                modelProvider: .cerebras,
                model: "gemma-4-31b"
            )
        )
        let appState = AppState(backendClient: client)
        appState.apply(
            CueSessionState(
                sessionID: "session-123",
                phase: .awaitingWorkflowApproval
            )
        )

        await appState.setYoloMode(true)

        XCTAssertEqual(client.yoloModeRequests, [true])
        XCTAssertTrue(appState.yoloMode)
        XCTAssertFalse(appState.pendingApproval)
    }

    @MainActor
    func testRefreshBackendHealthSyncsProviderState() async {
        let client = StubBackendClient(
            healthResponse: CueHealthResponse(
                status: "ok",
                app: "cue",
                yoloMode: false,
                modelProvider: .openrouter,
                model: "google/gemma-4-31b-it:free"
            )
        )
        let appState = AppState(backendClient: client)

        await appState.refreshBackendHealth()

        XCTAssertEqual(appState.backendHealth, .healthy)
        XCTAssertEqual(appState.modelProvider, .openrouter)
        XCTAssertEqual(appState.activeModel, "google/gemma-4-31b-it:free")
    }

    @MainActor
    func testProviderToggleUpdatesBackendMode() async {
        let client = StubBackendClient(
            modeResponse: CueModeResponse(
                yoloMode: false,
                modelProvider: .openrouter,
                model: "google/gemma-4-31b-it:free"
            )
        )
        let appState = AppState(backendClient: client)

        await appState.setModelProvider(.openrouter)

        XCTAssertEqual(client.modeRequests, [
            StubBackendClient.ModeRequest(yoloMode: nil, modelProvider: .openrouter)
        ])
        XCTAssertEqual(appState.modelProvider, .openrouter)
        XCTAssertEqual(appState.activeModel, "google/gemma-4-31b-it:free")
    }

    @MainActor
    func testProviderToggleRevertsWhenBackendModeUpdateFails() async {
        let client = StubBackendClient(modeError: StubBackendClient.StubError.modeFailed)
        let appState = AppState(backendClient: client)
        appState.modelProvider = .cerebras
        appState.activeModel = "gemma-4-31b"

        await appState.setModelProvider(.openrouter)

        XCTAssertEqual(appState.modelProvider, .cerebras)
        XCTAssertEqual(appState.activeModel, "gemma-4-31b")
        XCTAssertEqual(appState.phase, .error)
        XCTAssertNotNil(appState.lastErrorMessage)
    }

    @MainActor
    func testSpeechPreferencesPersistVoiceRateAndPitch() {
        let suiteName = "CueSpeechPreferences-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let store = SpeechPreferenceStore(userDefaults: defaults)
        let expected = SpeechPreferences(
            voiceIdentifier: "com.apple.voice.compact.en-US.Samantha",
            rate: 0.42,
            pitchMultiplier: 1.18
        )

        store.save(expected)

        XCTAssertEqual(store.load(), expected)
    }

    @MainActor
    func testSpeechControllerAppliesSelectedVoiceRateAndPitch() {
        guard let voiceIdentifier = AVSpeechSynthesisVoice.speechVoices().first?.identifier else {
            XCTFail("Expected macOS to expose at least one speech voice.")
            return
        }
        let synthesizer = CapturingSpeechSynthesizer()
        let controller = SpeechController(synthesizer: synthesizer)
        let preferences = SpeechPreferences(
            voiceIdentifier: voiceIdentifier,
            rate: 0.42,
            pitchMultiplier: 1.18
        )

        controller.speak("Cue narration", enabled: true, preferences: preferences)

        let utterance = synthesizer.spokenUtterances.first
        XCTAssertEqual(utterance?.speechString, "Cue narration")
        XCTAssertEqual(utterance?.voice?.identifier, preferences.voiceIdentifier)
        XCTAssertEqual(utterance?.rate ?? 0, preferences.rate, accuracy: 0.001)
        XCTAssertEqual(utterance?.pitchMultiplier ?? 0, preferences.pitchMultiplier, accuracy: 0.001)
    }
}

private final class CapturingSpeechSynthesizer: AVSpeechSynthesizer {
    private(set) var spokenUtterances: [AVSpeechUtterance] = []

    override func speak(_ utterance: AVSpeechUtterance) {
        spokenUtterances.append(utterance)
    }
}

private final class DeferredAppStateVoicePermissionRequester: VoicePermissionRequesting, @unchecked Sendable {
    private var speechContinuation: CheckedContinuation<Bool, Never>?
    private var microphoneContinuation: CheckedContinuation<Bool, Never>?

    func requestSpeechRecognitionPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            speechContinuation = continuation
        }
    }

    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            microphoneContinuation = continuation
        }
    }

    func resolve(granted: Bool) {
        speechContinuation?.resume(returning: granted)
        speechContinuation = nil
        microphoneContinuation?.resume(returning: granted)
        microphoneContinuation = nil
    }
}

private extension CueSessionState {
    func withSessionID(_ sessionID: String) -> CueSessionState {
        CueSessionState(
            sessionID: sessionID,
            phase: phase,
            workflowPlan: workflowPlan,
            currentStepID: currentStepID,
            verifiedSteps: verifiedSteps,
            lastVerification: lastVerification,
            narration: narration,
            stateSummary: stateSummary,
            focusStatus: focusStatus,
            risk: risk,
            policyDecision: policyDecision,
            confirmationPrompt: confirmationPrompt,
            timing: timing,
            auditSummary: auditSummary,
            auditEvents: auditEvents
        )
    }
}

private final class StubBackendClient: BackendClientProtocol, @unchecked Sendable {
    struct ChatRequest: Equatable {
        let command: String
        let conversationID: String?
    }

    struct ModeRequest: Equatable {
        let yoloMode: Bool?
        let modelProvider: CueModelProvider?
    }

    enum StubError: Error {
        case modeFailed
    }

    private let healthResponse: CueHealthResponse
    private let chatResponse: CueChatResponse
    private let approveResponse: CueSessionState
    private let nextResponse: CueSessionState
    private let modeResponse: CueModeResponse
    private let modeError: Error?
    private(set) var chatRequests: [ChatRequest] = []
    private(set) var approveRequests: [String] = []
    private(set) var nextRequests: [String] = []
    private(set) var yoloModeRequests: [Bool] = []
    private(set) var modeRequests: [ModeRequest] = []

    init(
        healthResponse: CueHealthResponse = CueHealthResponse(
            status: "ok",
            app: "cue",
            yoloMode: false,
            modelProvider: .cerebras,
            model: "gemma-4-31b"
        ),
        chatResponse: CueChatResponse = CueChatResponse(
            conversationID: "conversation-default",
            assistantMessage: "Ready.",
            mode: .conversation,
            session: nil,
            suggestedReplies: []
        ),
        approveResponse: CueSessionState = CueSessionState(
            sessionID: "approved",
            phase: .previewReady
        ),
        nextResponse: CueSessionState = CueSessionState(
            sessionID: "next",
            phase: .completed
        ),
        modeResponse: CueModeResponse = CueModeResponse(
            yoloMode: false,
            modelProvider: .cerebras,
            model: "gemma-4-31b"
        ),
        modeError: Error? = nil
    ) {
        self.healthResponse = healthResponse
        self.chatResponse = chatResponse
        self.approveResponse = approveResponse
        self.nextResponse = nextResponse
        self.modeResponse = modeResponse
        self.modeError = modeError
    }

    func health() async throws -> CueHealthResponse {
        healthResponse
    }

    func preview(command: String) async throws -> CueWorkflowPreviewResponse {
        CueWorkflowPreviewResponse(session: CueSessionState(sessionID: "preview", phase: .previewReady))
    }

    func chat(command: String, conversationID: String?) async throws -> CueChatResponse {
        chatRequests.append(ChatRequest(command: command, conversationID: conversationID))
        return chatResponse
    }

    func approve(sessionID: String, actor: String) async throws -> CueSessionState {
        approveRequests.append(sessionID)
        return approveResponse.withSessionID(sessionID)
    }

    func next(sessionID: String) async throws -> CueSessionState {
        nextRequests.append(sessionID)
        return nextResponse.withSessionID(sessionID)
    }

    func requestReview(sessionID: String, actor: String) async throws -> CueSessionState {
        CueSessionState(sessionID: sessionID, phase: .awaitingReviewerApproval)
    }

    func confirmReviewer(
        sessionID: String,
        approved: Bool,
        actor: String,
        reason: String?
    ) async throws -> CueSessionState {
        CueSessionState(sessionID: sessionID, phase: approved ? .previewReady : .blocked)
    }

    func cancel(sessionID: String, reason: String) async throws -> CueSessionState {
        CueSessionState(sessionID: sessionID, phase: .cancelled)
    }

    func session(id sessionID: String) async throws -> CueSessionState {
        CueSessionState(sessionID: sessionID, phase: .previewReady)
    }

    func auditEvents(sessionID: String?) async throws -> [CueAuditEvent] {
        []
    }

    func setYoloMode(_ enabled: Bool) async throws -> CueModeResponse {
        yoloModeRequests.append(enabled)
        return try await setMode(yoloMode: enabled, modelProvider: nil)
    }

    func setMode(
        yoloMode: Bool?,
        modelProvider: CueModelProvider?
    ) async throws -> CueModeResponse {
        if let modeError {
            throw modeError
        }
        modeRequests.append(ModeRequest(yoloMode: yoloMode, modelProvider: modelProvider))
        return modeResponse
    }
}
