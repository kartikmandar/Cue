import Foundation
import XCTest
@testable import CueApp

final class BackendClientTests: XCTestCase {
    override func tearDown() {
        RecordingURLProtocol.reset()
        super.tearDown()
    }

    func testPreviewPostsCommandAndDecodesWorkflowState() async throws {
        let payload = """
        {
          "session_id": "session-123",
          "state": "awaiting_workflow_approval",
          "workflow_plan": {
            "workflow_id": "workflow-123",
            "narration": "Cue can do this after approval.",
            "workflow_required": true,
            "workflow_category": "document",
            "risk_level": "low",
            "approval_tier": "confirm_each_action",
            "confirmation_prompt": "Approve this workflow?",
            "expected_outcome": "Cue is visible.",
            "risk_reasons": [],
            "requires_reviewer_approval": false,
            "redaction_applied": true,
            "allowed_by_policy": true,
            "policy_reason": "Allowed for test.",
            "audit_event_summary": "TextEdit: type_text",
            "steps": [
              {
                "step_id": "step-1",
                "title": "Type Cue",
                "action": {
                  "action_type": "type_text",
                  "payload": { "text": "Cue" },
                  "reason": "Type approved text.",
                  "expected_app": "TextEdit",
                  "expected_window": "Untitled",
                  "expected_focus": "Document body",
                  "changes_state": true
                },
                "expected_outcome": "Cue is visible.",
                "verification_criteria": "Cue is visible in TextEdit."
              }
            ]
          },
          "current_step_id": "step-1",
          "verified_steps": [],
          "last_verification": null,
          "focus": {
            "active_app": "TextEdit",
            "active_window": "Untitled",
            "focused_element": {
              "status": "known",
              "role": "AXTextArea",
              "title": "Document body",
              "value": "Cue draft",
              "source": "test"
            },
            "cursor_position": {
              "status": "known",
              "x": 20,
              "y": 40,
              "source": "test"
            },
            "sources": ["test"]
          },
          "policy_decision": {
            "allowed": true,
            "approval_tier": "confirm_each_action",
            "reason": "Allowed for test.",
            "requires_reviewer_approval": false,
            "redaction_applied": true
          },
          "confirmation_prompt": "Approve this workflow?",
          "timing": {
            "model": "gemma-4-31b",
            "latency_ms": 220,
            "token_usage": 84,
            "action_loop_ms": 31,
            "verification_ms": 19,
            "backend_ms": 12
          },
          "audit_summary": ["TextEdit: type_text"],
          "audit_events": []
        }
        """
        RecordingURLProtocol.stub(
            path: "/session/preview",
            response: payload
        )
        let client = BackendClient(
            baseURL: URL(string: "http://127.0.0.1:8765")!,
            session: .recording
        )

        let response = try await client.preview(command: "Type Cue")

        let request = try XCTUnwrap(RecordingURLProtocol.lastRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/session/preview")
        XCTAssertEqual(try request.jsonBody()["request"] as? String, "Type Cue")
        XCTAssertEqual(response.session.phase, .awaitingWorkflowApproval)
        XCTAssertEqual(response.session.workflowPlan?.steps.first?.stepID, "step-1")
        XCTAssertEqual(response.session.workflowPlan?.steps.first?.action.actionType, "type_text")
        XCTAssertEqual(response.session.focusStatus?.activeApp, "TextEdit")
        XCTAssertEqual(response.session.policyDecision?.redactionApplied, true)
        XCTAssertEqual(response.session.timing?.model, "gemma-4-31b")
        XCTAssertEqual(response.session.timing?.latencyMS, 220)
        XCTAssertEqual(response.session.timing?.tokenUsage, 84)
        XCTAssertEqual(response.session.timing?.actionLoopMS, 31)
        XCTAssertEqual(response.session.timing?.verificationMS, 19)
    }

    func testWorkflowControlMethodsUseBackendRoutesAndDecodeResponses() async throws {
        let sessionPayload = """
        {
          "session_id": "session-123",
          "state": "completed",
          "workflow_plan": null,
          "current_step_id": null,
          "verified_steps": ["step-1"],
          "last_verification": {
            "status": "passed",
            "reason": "The text matched.",
            "expected": "Cue is visible.",
            "actual": "Cue is visible.",
            "next_recommendation": "Continue."
          },
          "focus": {
            "active_app": "TextEdit",
            "active_window": "Untitled",
            "focused_element": { "status": "known", "title": "Document body" },
            "cursor_position": { "status": "unknown", "reason": "not observed" },
            "sources": ["test"]
          },
          "policy_decision": {
            "allowed": true,
            "approval_tier": "inform_only",
            "reason": "No workflow policy decision is available.",
            "requires_reviewer_approval": false,
            "redaction_applied": false
          },
          "confirmation_prompt": null,
          "timing": { "backend_ms": 4 },
          "audit_summary": ["verified"],
          "audit_events": [
            {
              "timestamp": "2026-06-29T00:00:00Z",
              "event_type": "verification_result",
              "session_id": "session-123",
              "workflow_id": "workflow-123",
              "state": "completed",
              "current_step_id": null,
              "approval_tier": "inform_only",
              "policy_reason": "No workflow policy decision is available.",
              "verification_status": "passed",
              "summary": "verified"
            }
          ]
        }
        """
        RecordingURLProtocol.stub(path: "/session/next", response: sessionPayload)
        let client = BackendClient(
            baseURL: URL(string: "http://127.0.0.1:8765")!,
            session: .recording
        )

        let state = try await client.next(sessionID: "session-123")

        let request = try XCTUnwrap(RecordingURLProtocol.lastRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/session/next")
        XCTAssertEqual(try request.jsonBody()["session_id"] as? String, "session-123")
        XCTAssertEqual(state.phase, .completed)
        XCTAssertEqual(state.lastVerification?.status, "passed")
        XCTAssertEqual(state.auditEvents.first?.eventType, "verification_result")
    }

    func testSetYoloModePostsModeRequestAndDecodesResponse() async throws {
        RecordingURLProtocol.stub(
            path: "/mode",
            response: #"{"yolo_mode": true}"#
        )
        let client = BackendClient(
            baseURL: URL(string: "http://127.0.0.1:8765")!,
            session: .recording
        )

        let response = try await client.setYoloMode(true)

        let request = try XCTUnwrap(RecordingURLProtocol.lastRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/mode")
        XCTAssertEqual(try request.jsonBody()["yolo_mode"] as? Bool, true)
        XCTAssertEqual(response.yoloMode, true)
    }

    func testChatPostsCommandAndDecodesConversationResponse() async throws {
        let payload = """
        {
          "conversation_id": "conversation-123",
          "assistant_message": "I can do that. Approve opening TextEdit?",
          "mode": "action_preview",
          "session": {
            "session_id": "session-123",
            "state": "awaiting_workflow_approval",
            "workflow_plan": {
              "workflow_id": "workflow-123",
              "narration": "Cue can open TextEdit after approval.",
              "workflow_required": true,
              "workflow_category": "app_launch",
              "risk_level": "low",
              "approval_tier": "confirm_each_action",
              "confirmation_prompt": "Approve opening TextEdit?",
              "expected_outcome": "TextEdit is active.",
              "risk_reasons": [],
              "requires_reviewer_approval": false,
              "redaction_applied": false,
              "allowed_by_policy": true,
              "policy_reason": "Allowed for test.",
              "audit_event_summary": "TextEdit open previewed.",
              "steps": []
            },
            "current_step_id": null,
            "verified_steps": [],
            "last_verification": null,
            "narration": {
              "summary": "Approve opening TextEdit?",
              "speakable_text": "Approve opening TextEdit?",
              "redaction_applied": false
            },
            "focus": {
              "active_app": "CueApp",
              "active_window": "Cue",
              "focused_element": { "status": "known", "title": "Cue request" },
              "cursor_position": { "status": "unknown", "reason": "not observed" },
              "sources": ["test"]
            },
            "policy_decision": {
              "allowed": true,
              "approval_tier": "confirm_each_action",
              "reason": "Allowed for test.",
              "requires_reviewer_approval": false,
              "redaction_applied": false
            },
            "confirmation_prompt": "Approve opening TextEdit?",
            "timing": { "backend_ms": 5 },
            "audit_summary": ["TextEdit open previewed."],
            "audit_events": []
          },
          "suggested_replies": ["Approve", "Cancel"]
        }
        """
        RecordingURLProtocol.stub(path: "/chat", response: payload)
        let client = BackendClient(
            baseURL: URL(string: "http://127.0.0.1:8765")!,
            session: .recording
        )

        let response = try await client.chat(
            command: "Open TextEdit",
            conversationID: "conversation-123"
        )

        let request = try XCTUnwrap(RecordingURLProtocol.lastRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/chat")
        let body = try request.jsonBody()
        XCTAssertEqual(body["request"] as? String, "Open TextEdit")
        XCTAssertEqual(body["conversation_id"] as? String, "conversation-123")
        XCTAssertEqual(response.conversationID, "conversation-123")
        XCTAssertEqual(response.assistantMessage, "I can do that. Approve opening TextEdit?")
        XCTAssertEqual(response.mode, .actionPreview)
        XCTAssertEqual(response.session?.phase, .awaitingWorkflowApproval)
        XCTAssertEqual(response.suggestedReplies, ["Approve", "Cancel"])
    }

    func testAuditEventsDecodeEnvelope() async throws {
        RecordingURLProtocol.stub(
            path: "/audit/events",
            response: """
            {
              "events": [
                {
                  "timestamp": "2026-06-29T00:00:00Z",
                  "event_type": "preview",
                  "session_id": "session-123",
                  "workflow_id": "workflow-123",
                  "state": "awaiting_workflow_approval",
                  "current_step_id": "step-1",
                  "approval_tier": "confirm_each_action",
                  "policy_reason": "Allowed for test.",
                  "verification_status": "not_started",
                  "summary": "TextEdit: type_text"
                }
              ]
            }
            """
        )
        let client = BackendClient(
            baseURL: URL(string: "http://127.0.0.1:8765")!,
            session: .recording
        )

        let events = try await client.auditEvents(sessionID: "session-123")

        let request = try XCTUnwrap(RecordingURLProtocol.lastRequest)
        XCTAssertEqual(request.httpMethod, "GET")
        XCTAssertEqual(request.url?.path, "/audit/events")
        XCTAssertEqual(request.url?.query, "session_id=session-123")
        XCTAssertEqual(events.first?.summary, "TextEdit: type_text")
    }
}

private final class RecordingURLProtocol: URLProtocol {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var stubs: [String: Data] = [:]
    nonisolated(unsafe) private(set) static var lastRequest: URLRequest?
    nonisolated(unsafe) private(set) static var lastBody: Data?

    static func stub(path: String, response: String) {
        lock.lock()
        defer { lock.unlock() }
        stubs[path] = Data(response.utf8)
    }

    static func reset() {
        lock.lock()
        defer { lock.unlock() }
        stubs = [:]
        lastRequest = nil
        lastBody = nil
    }

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        Self.lock.lock()
        Self.lastRequest = request
        Self.lastBody = Self.bodyData(from: request)
        let path = request.url?.path ?? ""
        let data = Self.stubs[path] ?? Data("{}".utf8)
        Self.lock.unlock()

        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private static func bodyData(from request: URLRequest) -> Data? {
        if let httpBody = request.httpBody {
            return httpBody
        }
        guard let stream = request.httpBodyStream else {
            return nil
        }
        stream.open()
        defer { stream.close() }

        var data = Data()
        let bufferSize = 1_024
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer { buffer.deallocate() }

        while stream.hasBytesAvailable {
            let count = stream.read(buffer, maxLength: bufferSize)
            if count <= 0 {
                break
            }
            data.append(buffer, count: count)
        }
        return data
    }
}

private extension URLSession {
    static var recording: URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [RecordingURLProtocol.self]
        return URLSession(configuration: configuration)
    }
}

private extension URLRequest {
    func jsonBody() throws -> [String: Any] {
        let data = try XCTUnwrap(httpBody ?? RecordingURLProtocol.lastBody)
        let object = try JSONSerialization.jsonObject(with: data)
        return try XCTUnwrap(object as? [String: Any])
    }
}
