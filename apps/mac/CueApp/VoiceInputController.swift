import AVFoundation
import Foundation
import Speech

protocol VoicePermissionRequesting: Sendable {
    func requestSpeechRecognitionPermission() async -> Bool
    func requestMicrophonePermission() async -> Bool
}

struct SystemVoicePermissionRequester: VoicePermissionRequesting {
    func requestSpeechRecognitionPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }

    func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                continuation.resume(returning: granted)
            }
        }
    }
}

enum VoiceAudioTap {
    static func makeAppendHandler(
        for request: SFSpeechAudioBufferRecognitionRequest
    ) -> AVAudioNodeTapBlock {
        { [weak request] buffer, _ in
            request?.append(buffer)
        }
    }
}

enum VoiceInputState: String, Equatable {
    case idle
    case requestingPermission
    case listening
    case transcribing
    case unavailable
    case error
}

@MainActor
final class VoiceInputController: NSObject, ObservableObject {
    @Published private(set) var state: VoiceInputState = .idle
    @Published private(set) var transcript = ""
    @Published private(set) var errorMessage: String?

    var isListening: Bool {
        state == .listening
    }

    var isRecordingSessionActive: Bool {
        state == .requestingPermission || state == .listening
    }

    static func stateAfterRecognitionResult(
        isFinal: Bool,
        isAudioEngineRunning: Bool,
        transcript: String
    ) -> VoiceInputState {
        if isFinal {
            return .transcribing
        }
        if isAudioEngineRunning {
            return .listening
        }
        return transcript.isEmpty ? .idle : .transcribing
    }

    private let speechRecognizer: SFSpeechRecognizer?
    private let audioEngine: AVAudioEngine
    private let permissionRequester: any VoicePermissionRequesting
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var startRequestID: UUID?

    init(
        speechRecognizer: SFSpeechRecognizer? = SFSpeechRecognizer(),
        audioEngine: AVAudioEngine = AVAudioEngine(),
        permissionRequester: any VoicePermissionRequesting = SystemVoicePermissionRequester()
    ) {
        self.speechRecognizer = speechRecognizer
        self.audioEngine = audioEngine
        self.permissionRequester = permissionRequester
    }

    func startListening() {
        guard !isRecordingSessionActive else { return }
        let requestID = UUID()
        startRequestID = requestID
        state = .requestingPermission
        errorMessage = nil

        Task {
            guard let granted = await requestPermissions(for: requestID) else { return }
            guard granted else {
                state = .unavailable
                errorMessage = "Microphone or speech recognition permission is not available."
                return
            }

            do {
                try beginRecognition()
            } catch {
                state = .error
                errorMessage = error.localizedDescription
                stopAudio()
            }
        }
    }

    func stopListening() {
        guard isRecordingSessionActive else { return }
        startRequestID = nil
        recognitionRequest?.endAudio()
        stopAudio()
        state = transcript.isEmpty ? .idle : .transcribing
    }

    func cancelListening() {
        startRequestID = nil
        transcript = ""
        recognitionTask?.cancel()
        stopAudio()
        state = .idle
    }

    func clearTranscript() {
        transcript = ""
        if !isListening {
            state = .idle
        }
    }

    private func requestPermissions(for requestID: UUID) async -> Bool? {
        let speech = await permissionRequester.requestSpeechRecognitionPermission()
        guard startRequestID == requestID else { return nil }
        let microphone = await permissionRequester.requestMicrophonePermission()
        guard startRequestID == requestID else { return nil }
        return speech && microphone
    }

    private func beginRecognition() throws {
        guard let speechRecognizer else {
            startRequestID = nil
            state = .unavailable
            errorMessage = "Speech recognition is not available on this Mac."
            return
        }
        guard speechRecognizer.isAvailable else {
            startRequestID = nil
            state = .unavailable
            errorMessage = "Speech recognition is temporarily unavailable."
            return
        }

        recognitionTask?.cancel()
        recognitionTask = nil

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(
            onBus: 0,
            bufferSize: 1_024,
            format: format,
            block: VoiceAudioTap.makeAppendHandler(for: request)
        )

        audioEngine.prepare()
        try audioEngine.start()
        state = .listening
        startRequestID = nil

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self else { return }
                if let result {
                    self.transcript = result.bestTranscription.formattedString
                    self.state = Self.stateAfterRecognitionResult(
                        isFinal: result.isFinal,
                        isAudioEngineRunning: self.audioEngine.isRunning,
                        transcript: self.transcript
                    )
                }
                if let error {
                    self.errorMessage = error.localizedDescription
                    self.state = self.transcript.isEmpty ? .error : .transcribing
                    self.stopAudio()
                }
            }
        }
    }

    private func stopAudio() {
        if audioEngine.isRunning {
            audioEngine.stop()
        }
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest = nil
        recognitionTask = nil
    }
}
