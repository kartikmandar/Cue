import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            statusGrid
            backendSection
            commandSection
            if let lastErrorMessage = appState.lastErrorMessage {
                Text(lastErrorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .accessibilityLabel("Cue error: \(lastErrorMessage)")
            }
            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(minWidth: 620, minHeight: 520)
        .task {
            appState.refreshLocalStatus()
            if !ProcessInfo.processInfo.isRunningXCTest {
                await appState.refreshBackendHealth()
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Cue")
                    .font(.largeTitle.bold())
                Text("Native macOS shell")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            PhaseBadge(phase: appState.phase)
        }
    }

    private var statusGrid: some View {
        Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 12) {
            StatusRow(title: "Cua Driver", value: appState.onboardingStatus.cuaStatus.label)
            StatusRow(title: "Accessibility", value: appState.onboardingStatus.accessibilityPermission.label)
            StatusRow(title: "Screen Recording", value: appState.onboardingStatus.screenRecordingPermission.label)
            StatusRow(title: "Microphone", value: appState.onboardingStatus.microphonePermission.label)
            StatusRow(title: "Speech Recognition", value: appState.onboardingStatus.speechRecognitionPermission.label)
            StatusRow(title: "Cerebras API Key", value: appState.onboardingStatus.cerebrasAPIKeyStatus.label)
            StatusRow(title: "Strict Privacy", value: appState.onboardingStatus.strictPrivacyMode.enabledLabel)
            StatusRow(title: "Audit Redaction", value: appState.onboardingStatus.auditRedactionEnabled.enabledLabel)
            StatusRow(title: "Terminal Write", value: appState.onboardingStatus.terminalWriteDisabled ? "Disabled" : "Enabled")
            StatusRow(title: "Reviewer Mode", value: appState.onboardingStatus.reviewerModeEnabled.enabledLabel)
        }
        .padding(16)
        .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }

    private var backendSection: some View {
        HStack {
            Label(backendHealthLabel, systemImage: backendHealthIcon)
                .font(.headline)
            Spacer()
            Button("Refresh") {
                Task {
                    appState.refreshLocalStatus()
                    await appState.refreshBackendHealth()
                }
            }
            .keyboardShortcut("r", modifiers: [.command])
        }
    }

    private var commandSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker("Input Mode", selection: $appState.inputMode) {
                Text("Text").tag(CueInputMode.text)
                Text("Voice").tag(CueInputMode.voice)
            }
            .pickerStyle(.segmented)
            .accessibilityLabel("Input mode")

            TextField("Ask Cue what to do next", text: $appState.commandText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(3...5)

            HStack {
                Button("Preview") {
                    Task { await appState.previewCommand() }
                }
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(appState.inputMode == .voice)

                Toggle("Speech", isOn: $appState.speechEnabled)
                    .toggleStyle(.switch)

                Toggle("Privacy", isOn: Binding(
                    get: { appState.privacyMode == "strict" },
                    set: { appState.privacyMode = $0 ? "strict" : "standard" }
                ))
                .toggleStyle(.switch)
            }
        }
    }

    private var backendHealthLabel: String {
        switch appState.backendHealth {
        case .unknown:
            "Backend: Unknown"
        case .healthy:
            "Backend: Healthy"
        case .unavailable:
            "Backend: Unavailable"
        }
    }

    private var backendHealthIcon: String {
        switch appState.backendHealth {
        case .unknown:
            "questionmark.circle"
        case .healthy:
            "checkmark.circle"
        case .unavailable:
            "xmark.circle"
        }
    }
}

private struct StatusRow: View {
    let title: String
    let value: String

    var body: some View {
        GridRow {
            Text(title)
                .font(.callout.weight(.medium))
            Text(value)
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }
}

private struct PhaseBadge: View {
    let phase: CuePhase

    var body: some View {
        Text(phase.rawValue.replacingOccurrences(of: "_", with: " ").capitalized)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(.thinMaterial, in: Capsule())
            .accessibilityLabel("Cue phase \(phase.rawValue)")
    }
}

private extension Bool {
    var enabledLabel: String {
        self ? "Enabled" : "Disabled"
    }
}

private extension ProcessInfo {
    var isRunningXCTest: Bool {
        environment["XCTestConfigurationFilePath"] != nil
    }
}
