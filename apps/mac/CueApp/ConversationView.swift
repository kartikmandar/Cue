import SwiftUI

struct ConversationView: View {
    @EnvironmentObject private var appState: AppState
    @State private var voicePreferencesVisible = false

    var body: some View {
        VStack(spacing: 0) {
            topBar
            Divider()
            transcript
            Divider()
            VoiceComposerView(voiceInputController: appState.voiceInputController)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var topBar: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Cue")
                    .font(.system(size: 24, weight: .semibold, design: .rounded))
                Text("Voice-first desktop assistant")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Label(appState.phase.displayName, systemImage: appState.phase.iconName)
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(Color.accentColor.opacity(0.14), in: Capsule())
                .accessibilityLabel("Cue status \(appState.phase.displayName)")
            Toggle("Speech", isOn: $appState.speechEnabled)
                .toggleStyle(.switch)
                .accessibilityLabel("Speech narration")
            Toggle("YOLO", isOn: yoloModeBinding)
                .toggleStyle(.switch)
                .help("Run requested actions without approval or reviewer gates.")
                .accessibilityLabel("YOLO mode")
            Picker("Provider", selection: providerBinding) {
                ForEach(CueModelProvider.allCases) { provider in
                    Text(provider.displayName).tag(provider)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 210)
            .help("Choose which hosted Gemma provider Cue uses for chat and workflow planning.")
            .accessibilityLabel("Model provider")
            Button {
                voicePreferencesVisible.toggle()
            } label: {
                Label("Voice", systemImage: "speaker.wave.2")
            }
            .popover(isPresented: $voicePreferencesVisible, arrowEdge: .bottom) {
                VoicePreferencesView()
                    .environmentObject(appState)
                    .frame(width: 340)
                    .padding(16)
            }
            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    appState.detailsInspectorVisible.toggle()
                }
            } label: {
                Label(appState.detailsInspectorVisible ? "Hide Details" : "Details", systemImage: "sidebar.right")
            }
            .keyboardShortcut("i", modifiers: [.command])
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 14)
        .accessibilityElement(children: .contain)
    }

    private var yoloModeBinding: Binding<Bool> {
        Binding(
            get: { appState.yoloMode },
            set: { enabled in
                Task { await appState.setYoloMode(enabled) }
            }
        )
    }

    private var providerBinding: Binding<CueModelProvider> {
        Binding(
            get: { appState.modelProvider },
            set: { provider in
                Task { await appState.setModelProvider(provider) }
            }
        )
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 14) {
                    ForEach(appState.conversationMessages) { message in
                        ConversationMessageView(message: message)
                            .id(message.id)
                    }
                }
                .padding(.horizontal, 22)
                .padding(.vertical, 18)
            }
            .onChange(of: appState.conversationMessages.count) { _, _ in
                if let lastID = appState.conversationMessages.last?.id {
                    withAnimation(.easeOut(duration: 0.16)) {
                        proxy.scrollTo(lastID, anchor: .bottom)
                    }
                }
            }
        }
    }
}

struct VoicePreferencesView: View {
    @EnvironmentObject private var appState: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Voice", systemImage: "speaker.wave.2")
                    .font(.headline)
                Spacer()
                Button {
                    appState.previewSpeechVoice()
                } label: {
                    Label("Preview", systemImage: "play.circle")
                }
            }

            Picker("Voice", selection: Binding(
                get: { appState.speechPreferences.voiceIdentifier ?? "" },
                set: { appState.setSpeechVoiceIdentifier($0.nilIfEmpty) }
            )) {
                Text("System Default").tag("")
                ForEach(appState.speechVoiceOptions) { voice in
                    Text(voice.displayName).tag(voice.identifier)
                }
            }
            .labelsHidden()

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Rate")
                    Spacer()
                    Text(rateLabel)
                        .foregroundStyle(.secondary)
                }
                Slider(
                    value: Binding(
                        get: { Double(appState.speechPreferences.rate) },
                        set: { appState.setSpeechRate(Float($0)) }
                    ),
                    in: Double(SpeechPreferences.minimumRate)...Double(SpeechPreferences.maximumRate)
                )
                .accessibilityLabel("Speech rate")
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Pitch")
                    Spacer()
                    Text(pitchLabel)
                        .foregroundStyle(.secondary)
                }
                Slider(
                    value: Binding(
                        get: { Double(appState.speechPreferences.pitchMultiplier) },
                        set: { appState.setSpeechPitchMultiplier(Float($0)) }
                    ),
                    in: Double(SpeechPreferences.minimumPitchMultiplier)...Double(SpeechPreferences.maximumPitchMultiplier)
                )
                .accessibilityLabel("Speech pitch")
            }

            HStack {
                Spacer()
                Button {
                    appState.resetSpeechPreferences()
                } label: {
                    Label("Reset", systemImage: "arrow.counterclockwise")
                }
            }
        }
        .font(.callout)
    }

    private var rateLabel: String {
        "\(Int((appState.speechPreferences.rate * 100).rounded()))%"
    }

    private var pitchLabel: String {
        String(format: "%.2fx", appState.speechPreferences.pitchMultiplier)
    }
}

private struct ConversationMessageView: View {
    let message: CueConversationMessage

    var body: some View {
        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 10) {
            HStack {
                if message.role == .user {
                    Spacer(minLength: 42)
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text(message.role == .user ? "You" : "Cue")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Text(message.text)
                        .font(.body)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(12)
                .frame(maxWidth: 520, alignment: .leading)
                .background(messageBackground, in: RoundedRectangle(cornerRadius: 8))
                if message.role == .assistant {
                    Spacer(minLength: 42)
                }
            }

            if message.hasActionCard, let session = message.session {
                ActionPreviewCard(session: session)
                    .frame(maxWidth: 620, alignment: .leading)
            }
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
        .accessibilityElement(children: .contain)
    }

    private var messageBackground: Color {
        switch message.role {
        case .user:
            Color.accentColor.opacity(0.18)
        case .assistant:
            Color(nsColor: .controlBackgroundColor)
        }
    }
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}

private struct ActionPreviewCard: View {
    @EnvironmentObject private var appState: AppState
    let session: CueSessionState

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Action Preview", systemImage: "checklist")
                .font(.headline)

            if let plan = session.workflowPlan {
                Text(plan.narration)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                ForEach(Array(plan.steps.enumerated()), id: \.element.id) { index, step in
                    HStack(alignment: .top, spacing: 10) {
                        Text("\(index + 1)")
                            .font(.caption.weight(.bold))
                            .frame(width: 22, height: 22)
                            .background(Color.accentColor.opacity(0.14), in: Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text(step.title)
                                .font(.callout.weight(.semibold))
                            Text(step.expectedOutcome)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            Text(confirmationText)
                .font(.callout)

            HStack(spacing: 10) {
                Button {
                    Task { await appState.approveWorkflow() }
                } label: {
                    Label("Approve", systemImage: "checkmark.seal")
                }
                .buttonStyle(.borderedProminent)
                .disabled(appState.yoloMode || !appState.pendingApproval || appState.phase.isBusy)

                Button {
                    Task { await appState.executeNextStep() }
                } label: {
                    Label("Do Next Step", systemImage: "arrow.right.circle")
                }
                .disabled(appState.currentSession == nil || appState.pendingApproval || appState.phase.isTerminal || appState.phase.isBusy)

                Button(role: .cancel) {
                    Task { await appState.cancelWorkflow() }
                } label: {
                    Label("Cancel", systemImage: "xmark.circle")
                }
                .disabled(appState.currentSession == nil)
            }
        }
        .padding(14)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }

    private var confirmationText: String {
        if appState.yoloMode {
            return "YOLO mode is on. Cue can run the next step without approval."
        }
        return session.confirmationPrompt ?? "Cue will ask before it changes state."
    }
}

private struct VoiceComposerView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var voiceInputController: VoiceInputController
    @State private var pushToTalkShortcutController: PushToTalkShortcutController?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if appState.inputMode == .voice {
                voiceControls
            } else {
                textControls
            }

            if let error = voiceInputController.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .accessibilityLabel("Voice input error: \(error)")
            }

            if let error = appState.lastErrorMessage {
                Label(error, systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .accessibilityLabel("Cue error: \(error)")
            }
        }
        .padding(18)
        .background(Color(nsColor: .controlBackgroundColor))
        .onChange(of: voiceInputController.transcript) { _, transcript in
            guard appState.inputMode == .voice else { return }
            appState.commandText = transcript
            submitVoiceCommandIfReady(voiceState: voiceInputController.state)
        }
        .onChange(of: voiceInputController.state) { _, state in
            submitVoiceCommandIfReady(voiceState: state)
        }
        .onAppear {
            installPushToTalkShortcut()
        }
        .onDisappear {
            pushToTalkShortcutController?.stop()
            pushToTalkShortcutController = nil
        }
        .onChange(of: appState.inputMode) { _, inputMode in
            if inputMode != .voice {
                pushToTalkShortcutController?.release()
            }
        }
    }

    private var voiceControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 14) {
                Button {
                    togglePushToTalk()
                } label: {
                    Label(microphoneTitle, systemImage: voiceInputController.isRecordingSessionActive ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.headline)
                        .frame(minWidth: 170, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .help("Click to start or stop listening. Hold Space to talk; release to stop.")
                .accessibilityLabel(microphoneTitle)

                VStack(alignment: .leading, spacing: 3) {
                    Text(voiceStatusText)
                        .font(.callout.weight(.semibold))
                    Text(appState.commandText.isEmpty ? "Your transcript will appear here." : appState.commandText)
                        .font(.body)
                        .foregroundStyle(appState.commandText.isEmpty ? .secondary : .primary)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
            }

            HStack(spacing: 10) {
                Button {
                    Task { await appState.sendChatCommand() }
                } label: {
                    Label("Send", systemImage: "paperplane.fill")
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(appState.commandText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || appState.phase.isBusy)

                Button {
                    appState.inputMode = .text
                } label: {
                    Label("Type Instead", systemImage: "keyboard")
                }

                Button {
                    voiceInputController.cancelListening()
                    appState.commandText = ""
                } label: {
                    Label("Clear", systemImage: "xmark.circle")
                }
                .disabled(appState.commandText.isEmpty && voiceInputController.transcript.isEmpty)
            }
        }
    }

    private var textControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField("Ask Cue what to do next", text: $appState.commandText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(2...5)
                .accessibilityLabel("Cue request")

            HStack(spacing: 10) {
                Button {
                    Task { await appState.sendChatCommand() }
                } label: {
                    Label("Send", systemImage: "paperplane.fill")
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.return, modifiers: [.command])
                .disabled(appState.commandText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || appState.phase.isBusy)

                Button {
                    appState.inputMode = .voice
                } label: {
                    Label("Use Voice", systemImage: "waveform")
                }
            }
        }
    }

    private var microphoneTitle: String {
        voiceInputController.isRecordingSessionActive ? "Stop Listening" : "Push to Talk"
    }

    private var voiceStatusText: String {
        switch voiceInputController.state {
        case .idle:
            "Ready for voice"
        case .requestingPermission:
            "Requesting microphone access"
        case .listening:
            "Listening"
        case .transcribing:
            "Transcript ready"
        case .unavailable:
            "Voice unavailable"
        case .error:
            "Voice error"
        }
    }

    private func installPushToTalkShortcut() {
        guard pushToTalkShortcutController == nil else { return }
        let controller = PushToTalkShortcutController(
            isEnabled: {
                appState.inputMode == .voice
            },
            startListening: {
                beginPushToTalk()
            },
            stopListening: {
                endPushToTalk()
            }
        )
        controller.start()
        pushToTalkShortcutController = controller
    }

    private func pressPushToTalk() {
        if let pushToTalkShortcutController {
            pushToTalkShortcutController.press()
        } else {
            beginPushToTalk()
        }
    }

    private func releasePushToTalk() {
        if let pushToTalkShortcutController {
            pushToTalkShortcutController.release()
        } else {
            endPushToTalk()
        }
    }

    private func togglePushToTalk() {
        if let pushToTalkShortcutController {
            pushToTalkShortcutController.toggle()
        } else if voiceInputController.isRecordingSessionActive {
            endPushToTalk()
        } else {
            beginPushToTalk()
        }
    }

    private func beginPushToTalk() {
        guard appState.inputMode == .voice else { return }
        appState.prepareForVoiceCommandCapture()
        voiceInputController.clearTranscript()
        appState.commandText = ""
        voiceInputController.startListening()
    }

    private func endPushToTalk() {
        voiceInputController.stopListening()
    }

    private func submitVoiceCommandIfReady(voiceState: VoiceInputState) {
        Task {
            await appState.sendVoiceCommandIfTranscriptReady(voiceState: voiceState)
        }
    }
}
