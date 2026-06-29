import Foundation

enum CueConversationRole: String, Equatable, Identifiable {
    case user
    case assistant

    var id: String { rawValue }
}

struct CueConversationMessage: Equatable, Identifiable {
    let id: UUID
    let role: CueConversationRole
    let text: String
    let mode: CueChatMode
    let session: CueSessionState?
    let suggestedReplies: [String]
    let createdAt: Date

    init(
        id: UUID = UUID(),
        role: CueConversationRole,
        text: String,
        mode: CueChatMode = .conversation,
        session: CueSessionState? = nil,
        suggestedReplies: [String] = [],
        createdAt: Date = Date()
    ) {
        self.id = id
        self.role = role
        self.text = text
        self.mode = mode
        self.session = session
        self.suggestedReplies = suggestedReplies
        self.createdAt = createdAt
    }

    var hasActionCard: Bool {
        mode == .actionPreview && session != nil
    }

    static func welcome() -> CueConversationMessage {
        CueConversationMessage(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            role: .assistant,
            text: "Hi, I am Cue. Hold the microphone and tell me what you want to do, or type if you prefer."
        )
    }
}
