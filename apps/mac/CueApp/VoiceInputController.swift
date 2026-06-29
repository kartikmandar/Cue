import AVFoundation
import Foundation
import Speech

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
        state == .listening || state == .transcribing
    }

    private let speechRecognizer: SFSpeechRecognizer?
    private let audioEngine: AVAudioEngine
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?

    init(
        speechRecognizer: SFSpeechRecognizer? = SFSpeechRecognizer(),
        audioEngine: AVAudioEngine = AVAudioEngine()
    ) {
        self.speechRecognizer = speechRecognizer
        self.audioEngine = audioEngine
    }

    func startListening() {
        guard !isListening else { return }
        state = .requestingPermission
        errorMessage = nil

        Task {
            let granted = await requestPermissions()
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
        guard isListening || state == .requestingPermission else { return }
        recognitionRequest?.endAudio()
        stopAudio()
        state = transcript.isEmpty ? .idle : .transcribing
    }

    func cancelListening() {
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

    private func requestPermissions() async -> Bool {
        async let speechGranted = requestSpeechRecognitionPermission()
        async let microphoneGranted = requestMicrophonePermission()
        let speech = await speechGranted
        let microphone = await microphoneGranted
        return speech && microphone
    }

    private func requestSpeechRecognitionPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }

    private func requestMicrophonePermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    private func beginRecognition() throws {
        guard let speechRecognizer else {
            state = .unavailable
            errorMessage = "Speech recognition is not available on this Mac."
            return
        }
        guard speechRecognizer.isAvailable else {
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
        inputNode.installTap(onBus: 0, bufferSize: 1_024, format: format) { [weak request] buffer, _ in
            request?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
        state = .listening

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                guard let self else { return }
                if let result {
                    self.transcript = result.bestTranscription.formattedString
                    self.state = result.isFinal ? .transcribing : .listening
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
