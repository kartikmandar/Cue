import AVFoundation
import Speech
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

    @MainActor
    func testStartListeningHandlesPermissionCallbacksFromBackgroundQueue() async throws {
        let controller = VoiceInputController(
            speechRecognizer: nil,
            permissionRequester: BackgroundQueueVoicePermissionRequester()
        )

        controller.startListening()

        try await waitUntil {
            controller.state == .unavailable
        }
        XCTAssertEqual(
            controller.errorMessage,
            "Speech recognition is not available on this Mac."
        )
    }

    func testAudioTapHandlerCanRunOffMainQueue() async {
        let request = SFSpeechAudioBufferRecognitionRequest()
        let handler = VoiceAudioTap.makeAppendHandler(for: request)
        let format = AVAudioFormat(standardFormatWithSampleRate: 44_100, channels: 1)!
        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 1)!
        buffer.frameLength = 1
        let callbackReturned = expectation(description: "audio tap callback returned")

        DispatchQueue.global(qos: .userInitiated).async {
            handler(buffer, AVAudioTime(sampleTime: 0, atRate: 44_100))
            callbackReturned.fulfill()
        }

        await fulfillment(of: [callbackReturned], timeout: 1)
    }

    @MainActor
    private func waitUntil(
        timeout: TimeInterval = 2,
        condition: @escaping @MainActor () -> Bool
    ) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition() && Date() < deadline {
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTAssertTrue(condition())
    }
}

private struct BackgroundQueueVoicePermissionRequester: VoicePermissionRequesting {
    func requestSpeechRecognitionPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(returning: true)
            }
        }
    }

    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(returning: true)
            }
        }
    }
}
