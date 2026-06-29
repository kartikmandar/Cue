import XCTest
@testable import CueApp

final class VoiceInputControllerTests: XCTestCase {
    @MainActor
    func testVoiceInputControllerStartsIdleWithEmptyTranscript() {
        let controller = VoiceInputController()

        XCTAssertEqual(controller.state, .idle)
        XCTAssertEqual(controller.transcript, "")
        XCTAssertFalse(controller.isListening)
    }

    @MainActor
    func testAppStateOwnsInjectedVoiceInputController() {
        let controller = VoiceInputController()
        let appState = AppState(voiceInputController: controller)

        XCTAssertTrue(appState.voiceInputController === controller)
    }
}
