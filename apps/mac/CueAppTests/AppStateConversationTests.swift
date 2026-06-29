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

    private let chatResponse: CueChatResponse
    private let approveResponse: CueSessionState
    private let nextResponse: CueSessionState
    private(set) var chatRequests: [ChatRequest] = []
    private(set) var approveRequests: [String] = []
    private(set) var nextRequests: [String] = []

    init(
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
        )
    ) {
        self.chatResponse = chatResponse
        self.approveResponse = approveResponse
        self.nextResponse = nextResponse
    }

    func health() async throws -> CueHealthResponse {
        CueHealthResponse(status: "ok", app: "cue")
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
}
