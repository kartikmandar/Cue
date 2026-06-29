import SwiftUI

struct ConversationView: View {
    @EnvironmentObject private var appState: AppState

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

            Text(session.confirmationPrompt ?? "Cue will ask before it changes state.")
                .font(.callout)

            HStack(spacing: 10) {
                Button {
                    Task { await appState.approveWorkflow() }
                } label: {
                    Label("Approve", systemImage: "checkmark.seal")
                }
                .buttonStyle(.borderedProminent)
                .disabled(!appState.pendingApproval || appState.phase.isBusy)

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
}

private struct VoiceComposerView: View {
    @EnvironmentObject private var appState: AppState
    @ObservedObject var voiceInputController: VoiceInputController

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
        }
    }

    private var voiceControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 14) {
                Button {
                    toggleListening()
                } label: {
                    Label(microphoneTitle, systemImage: voiceInputController.isListening ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.headline)
                        .frame(minWidth: 170, minHeight: 44)
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.space, modifiers: [.command, .shift])
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
        voiceInputController.isListening ? "Stop Listening" : "Push to Talk"
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

    private func toggleListening() {
        if voiceInputController.isListening || voiceInputController.state == .requestingPermission {
            voiceInputController.stopListening()
        } else {
            voiceInputController.clearTranscript()
            appState.commandText = ""
            voiceInputController.startListening()
        }
    }
}
