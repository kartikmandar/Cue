import SwiftUI

struct InputModePicker: View {
    @Binding var selection: CueInputMode
    let voiceEnabled: Bool

    var body: some View {
        HStack(spacing: 8) {
            modeButton(.text, title: "Text", systemImage: "keyboard")
            modeButton(.voice, title: "Voice", systemImage: "waveform")
                .disabled(!voiceEnabled)
            if !voiceEnabled {
                Text("Voice disabled")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .contain)
    }

    private func modeButton(_ mode: CueInputMode, title: String, systemImage: String) -> some View {
        Button {
            selection = mode
        } label: {
            Label(title, systemImage: systemImage)
                .frame(minWidth: 92)
        }
        .buttonStyle(.bordered)
        .controlSize(.large)
        .background(selection == mode ? Color.accentColor.opacity(0.12) : Color.clear, in: RoundedRectangle(cornerRadius: 7))
        .accessibilityLabel("\(title) input mode")
    }
}
