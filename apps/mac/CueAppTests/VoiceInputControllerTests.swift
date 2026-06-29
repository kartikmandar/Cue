import AVFoundation
import AppKit
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

    @MainActor
    func testStopDuringPermissionRequestCancelsPendingStart() async throws {
        let permissionRequester = DeferredVoicePermissionRequester()
        let controller = VoiceInputController(
            speechRecognizer: nil,
            permissionRequester: permissionRequester
        )

        controller.startListening()
        XCTAssertEqual(controller.state, .requestingPermission)

        controller.stopListening()
        XCTAssertEqual(controller.state, .idle)

        permissionRequester.resolve(granted: true)
        try await Task.sleep(nanoseconds: 20_000_000)

        XCTAssertEqual(controller.state, .idle)
        XCTAssertNil(controller.errorMessage)
    }

    @MainActor
    func testPushToTalkShortcutStartsOnceAndStopsOnRelease() {
        var starts = 0
        var stops = 0
        let shortcut = PushToTalkShortcutController(
            isEnabled: { true },
            startListening: { starts += 1 },
            stopListening: { stops += 1 }
        )

        XCTAssertTrue(
            shortcut.handleKeyEvent(
                type: .keyDown,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [],
                isRepeat: false
            )
        )
        XCTAssertTrue(
            shortcut.handleKeyEvent(
                type: .keyDown,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [],
                isRepeat: true
            )
        )
        XCTAssertEqual(starts, 1)
        XCTAssertEqual(stops, 0)

        XCTAssertTrue(
            shortcut.handleKeyEvent(
                type: .keyUp,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [],
                isRepeat: false
            )
        )

        XCTAssertEqual(starts, 1)
        XCTAssertEqual(stops, 1)
    }

    @MainActor
    func testPushToTalkShortcutToggleStartsAndStopsRecording() {
        var starts = 0
        var stops = 0
        let shortcut = PushToTalkShortcutController(
            isEnabled: { true },
            startListening: { starts += 1 },
            stopListening: { stops += 1 }
        )

        shortcut.toggle()
        XCTAssertEqual(starts, 1)
        XCTAssertEqual(stops, 0)

        shortcut.toggle()
        XCTAssertEqual(starts, 1)
        XCTAssertEqual(stops, 1)
    }

    @MainActor
    func testLatePartialRecognitionResultAfterStopDoesNotReturnToListening() {
        XCTAssertEqual(
            VoiceInputController.stateAfterRecognitionResult(
                isFinal: false,
                isAudioEngineRunning: false,
                transcript: "Open Notes"
            ),
            .transcribing
        )
    }

    @MainActor
    func testPushToTalkShortcutIgnoresModifiedSpaceButStopsAfterDisable() {
        var starts = 0
        var stops = 0
        var enabled = true
        let shortcut = PushToTalkShortcutController(
            isEnabled: { enabled },
            startListening: { starts += 1 },
            stopListening: { stops += 1 }
        )

        XCTAssertFalse(
            shortcut.handleKeyEvent(
                type: .keyDown,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [.command, .shift],
                isRepeat: false
            )
        )
        XCTAssertEqual(starts, 0)

        XCTAssertTrue(
            shortcut.handleKeyEvent(
                type: .keyDown,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [],
                isRepeat: false
            )
        )
        enabled = false
        XCTAssertTrue(
            shortcut.handleKeyEvent(
                type: .keyUp,
                keyCode: PushToTalkShortcutController.spaceKeyCode,
                modifierFlags: [],
                isRepeat: false
            )
        )

        XCTAssertEqual(starts, 1)
        XCTAssertEqual(stops, 1)
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

private final class DeferredVoicePermissionRequester: VoicePermissionRequesting, @unchecked Sendable {
    private var speechContinuation: CheckedContinuation<Bool, Never>?
    private var microphoneContinuation: CheckedContinuation<Bool, Never>?
    private var resolvedGrant: Bool?

    func requestSpeechRecognitionPermission() async -> Bool {
        if let resolvedGrant {
            return resolvedGrant
        }
        return await withCheckedContinuation { continuation in
            speechContinuation = continuation
        }
    }

    func requestMicrophonePermission() async -> Bool {
        if let resolvedGrant {
            return resolvedGrant
        }
        return await withCheckedContinuation { continuation in
            microphoneContinuation = continuation
        }
    }

    func resolve(granted: Bool) {
        resolvedGrant = granted
        speechContinuation?.resume(returning: granted)
        speechContinuation = nil
        microphoneContinuation?.resume(returning: granted)
        microphoneContinuation = nil
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
