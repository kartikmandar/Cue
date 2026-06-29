import AVFoundation
import Foundation

struct SpeechVoiceOption: Identifiable, Equatable {
    let identifier: String
    let name: String
    let language: String

    var id: String { identifier }

    var displayName: String {
        "\(name) (\(language))"
    }
}

struct SpeechPreferences: Equatable {
    static let minimumRate: Float = 0.28
    static let maximumRate: Float = 0.68
    static let defaultRate: Float = 0.46
    static let minimumPitchMultiplier: Float = 0.70
    static let maximumPitchMultiplier: Float = 1.35
    static let defaultPitchMultiplier: Float = 1.0
    static let defaults = SpeechPreferences()

    var voiceIdentifier: String?
    var rate: Float
    var pitchMultiplier: Float

    init(
        voiceIdentifier: String? = nil,
        rate: Float = Self.defaultRate,
        pitchMultiplier: Float = Self.defaultPitchMultiplier
    ) {
        self.voiceIdentifier = voiceIdentifier?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        self.rate = min(max(rate, Self.minimumRate), Self.maximumRate)
        self.pitchMultiplier = min(max(pitchMultiplier, Self.minimumPitchMultiplier), Self.maximumPitchMultiplier)
    }
}

final class SpeechPreferenceStore {
    private enum Key {
        static let voiceIdentifier = "cue.speech.voiceIdentifier"
        static let rate = "cue.speech.rate"
        static let pitchMultiplier = "cue.speech.pitchMultiplier"
    }

    private let userDefaults: UserDefaults

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
    }

    func load() -> SpeechPreferences {
        SpeechPreferences(
            voiceIdentifier: userDefaults.string(forKey: Key.voiceIdentifier),
            rate: userDefaults.object(forKey: Key.rate) as? Float ?? SpeechPreferences.defaultRate,
            pitchMultiplier: userDefaults.object(forKey: Key.pitchMultiplier) as? Float
                ?? SpeechPreferences.defaultPitchMultiplier
        )
    }

    func save(_ preferences: SpeechPreferences) {
        if let voiceIdentifier = preferences.voiceIdentifier {
            userDefaults.set(voiceIdentifier, forKey: Key.voiceIdentifier)
        } else {
            userDefaults.removeObject(forKey: Key.voiceIdentifier)
        }
        userDefaults.set(preferences.rate, forKey: Key.rate)
        userDefaults.set(preferences.pitchMultiplier, forKey: Key.pitchMultiplier)
    }
}

@MainActor
final class SpeechController: NSObject, ObservableObject {
    private let synthesizer: AVSpeechSynthesizer

    init(synthesizer: AVSpeechSynthesizer = AVSpeechSynthesizer()) {
        self.synthesizer = synthesizer
    }

    static func availableVoices() -> [SpeechVoiceOption] {
        AVSpeechSynthesisVoice.speechVoices()
            .map {
                SpeechVoiceOption(identifier: $0.identifier, name: $0.name, language: $0.language)
            }
            .sorted {
                if $0.language == $1.language {
                    return $0.name.localizedStandardCompare($1.name) == .orderedAscending
                }
                return $0.language.localizedStandardCompare($1.language) == .orderedAscending
            }
    }

    func speak(_ text: String?, enabled: Bool, preferences: SpeechPreferences = .defaults) {
        guard enabled, let text else { return }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        let utterance = AVSpeechUtterance(string: trimmed)
        utterance.rate = preferences.rate
        utterance.pitchMultiplier = preferences.pitchMultiplier
        if let voiceIdentifier = preferences.voiceIdentifier,
           let voice = AVSpeechSynthesisVoice(identifier: voiceIdentifier) {
            utterance.voice = voice
        }
        utterance.prefersAssistiveTechnologySettings = true
        synthesizer.speak(utterance)
    }

    func stop() {
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
    }
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}
