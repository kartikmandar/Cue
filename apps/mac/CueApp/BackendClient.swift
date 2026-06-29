import Foundation

protocol BackendClientProtocol: Sendable {
    func health() async throws -> CueHealthResponse
    func preview(command: String) async throws -> CueWorkflowPreviewResponse
    func chat(command: String, conversationID: String?) async throws -> CueChatResponse
    func approve(sessionID: String, actor: String) async throws -> CueSessionState
    func next(sessionID: String) async throws -> CueSessionState
    func requestReview(sessionID: String, actor: String) async throws -> CueSessionState
    func confirmReviewer(
        sessionID: String,
        approved: Bool,
        actor: String,
        reason: String?
    ) async throws -> CueSessionState
    func cancel(sessionID: String, reason: String) async throws -> CueSessionState
    func session(id sessionID: String) async throws -> CueSessionState
    func auditEvents(sessionID: String?) async throws -> [CueAuditEvent]
    func setYoloMode(_ enabled: Bool) async throws -> CueModeResponse
}

extension BackendClientProtocol {
    func chat(command: String) async throws -> CueChatResponse {
        try await chat(command: command, conversationID: nil)
    }

    func approve(sessionID: String) async throws -> CueSessionState {
        try await approve(sessionID: sessionID, actor: "user")
    }

    func requestReview(sessionID: String) async throws -> CueSessionState {
        try await requestReview(sessionID: sessionID, actor: "guardian")
    }

    func confirmReviewer(
        sessionID: String,
        approved: Bool
    ) async throws -> CueSessionState {
        try await confirmReviewer(sessionID: sessionID, approved: approved, actor: "guardian", reason: nil)
    }

    func cancel(sessionID: String) async throws -> CueSessionState {
        try await cancel(sessionID: sessionID, reason: "Workflow cancelled.")
    }
}

final class BackendClient: @unchecked Sendable {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(
        baseURL: URL = URL(string: "http://127.0.0.1:8765")!,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    func health() async throws -> CueHealthResponse {
        try await send(path: "/health")
    }

    func preview(command: String) async throws -> CueWorkflowPreviewResponse {
        try await send(
            path: "/session/preview",
            method: "POST",
            body: PreviewRequest(request: command)
        )
    }

    func chat(command: String, conversationID: String? = nil) async throws -> CueChatResponse {
        try await send(
            path: "/chat",
            method: "POST",
            body: ChatRequest(request: command, conversationID: conversationID)
        )
    }

    func approve(sessionID: String, actor: String = "user") async throws -> CueSessionState {
        try await send(
            path: "/session/approve",
            method: "POST",
            body: ActorSessionRequest(sessionID: sessionID, actor: actor)
        )
    }

    func next(sessionID: String) async throws -> CueSessionState {
        try await send(
            path: "/session/next",
            method: "POST",
            body: SessionRequest(sessionID: sessionID)
        )
    }

    func requestReview(sessionID: String, actor: String = "guardian") async throws -> CueSessionState {
        try await send(
            path: "/session/request-review",
            method: "POST",
            body: ActorSessionRequest(sessionID: sessionID, actor: actor)
        )
    }

    func confirmReviewer(
        sessionID: String,
        approved: Bool,
        actor: String = "guardian",
        reason: String? = nil
    ) async throws -> CueSessionState {
        try await send(
            path: "/session/confirm-reviewer",
            method: "POST",
            body: ConfirmReviewerRequest(
                sessionID: sessionID,
                approved: approved,
                actor: actor,
                reason: reason
            )
        )
    }

    func cancel(
        sessionID: String,
        reason: String = "Workflow cancelled."
    ) async throws -> CueSessionState {
        try await send(
            path: "/session/cancel",
            method: "POST",
            body: CancelRequest(sessionID: sessionID, reason: reason)
        )
    }

    func session(id sessionID: String) async throws -> CueSessionState {
        try await send(path: "/session/\(sessionID.pathEscaped)")
    }

    func auditEvents(sessionID: String? = nil) async throws -> [CueAuditEvent] {
        let envelope: AuditEventsEnvelope = try await send(
            path: "/audit/events",
            queryItems: sessionID.map { [URLQueryItem(name: "session_id", value: $0)] } ?? []
        )
        return envelope.events
    }

    func setYoloMode(_ enabled: Bool) async throws -> CueModeResponse {
        try await send(
            path: "/mode",
            method: "POST",
            body: ModeRequest(yoloMode: enabled)
        )
    }

    private func send<Response: Decodable>(
        path: String,
        queryItems: [URLQueryItem] = []
    ) async throws -> Response {
        let request = try makeRequest(path: path, method: "GET", queryItems: queryItems)
        return try await perform(request)
    }

    private func send<Response: Decodable, Body: Encodable>(
        path: String,
        method: String,
        body: Body
    ) async throws -> Response {
        var request = try makeRequest(path: path, method: method)
        request.httpBody = try encoder.encode(body)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await perform(request)
    }

    private func makeRequest(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = []
    ) throws -> URLRequest {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw BackendClientError.invalidBaseURL(baseURL.absoluteString)
        }
        components.path = path
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        guard let url = components.url else {
            throw BackendClientError.invalidPath(path)
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 10
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        return request
    }

    private func perform<Response: Decodable>(_ request: URLRequest) async throws -> Response {
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BackendClientError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw BackendClientError.httpStatus(httpResponse.statusCode)
        }
        do {
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw BackendClientError.decodingFailed(error)
        }
    }
}

extension BackendClient: BackendClientProtocol {}

enum BackendClientError: Error, LocalizedError, Equatable {
    case invalidBaseURL(String)
    case invalidPath(String)
    case invalidResponse
    case httpStatus(Int)
    case decodingFailed(Error)

    static func == (lhs: BackendClientError, rhs: BackendClientError) -> Bool {
        switch (lhs, rhs) {
        case (.invalidBaseURL(let left), .invalidBaseURL(let right)):
            left == right
        case (.invalidPath(let left), .invalidPath(let right)):
            left == right
        case (.invalidResponse, .invalidResponse):
            true
        case (.httpStatus(let left), .httpStatus(let right)):
            left == right
        case (.decodingFailed, .decodingFailed):
            true
        default:
            false
        }
    }

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL(let value):
            "Invalid backend base URL: \(value)"
        case .invalidPath(let value):
            "Invalid backend path: \(value)"
        case .invalidResponse:
            "Cue backend returned a non-HTTP response."
        case .httpStatus(let code):
            "Cue backend returned HTTP \(code)."
        case .decodingFailed(let error):
            "Cue backend response could not be decoded: \(error.localizedDescription)"
        }
    }
}

private struct PreviewRequest: Encodable {
    let request: String
}

private struct ChatRequest: Encodable {
    let request: String
    let conversationID: String?

    enum CodingKeys: String, CodingKey {
        case request
        case conversationID = "conversation_id"
    }
}

private struct SessionRequest: Encodable {
    let sessionID: String

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
    }
}

private struct ActorSessionRequest: Encodable {
    let sessionID: String
    let actor: String

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case actor
    }
}

private struct ConfirmReviewerRequest: Encodable {
    let sessionID: String
    let approved: Bool
    let actor: String
    let reason: String?

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case approved
        case actor
        case reason
    }
}

private struct CancelRequest: Encodable {
    let sessionID: String
    let reason: String

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case reason
    }
}

private struct ModeRequest: Encodable {
    let yoloMode: Bool

    enum CodingKeys: String, CodingKey {
        case yoloMode = "yolo_mode"
    }
}

private struct AuditEventsEnvelope: Decodable {
    let events: [CueAuditEvent]
}

private extension String {
    var pathEscaped: String {
        addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? self
    }
}
