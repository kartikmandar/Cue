import Foundation

enum CuePhase: String, Codable, CaseIterable, Equatable, Identifiable {
    case idle
    case previewReady = "preview_ready"
    case awaitingWorkflowApproval = "awaiting_workflow_approval"
    case awaitingStepApproval = "awaiting_step_approval"
    case awaitingReviewerApproval = "awaiting_reviewer_approval"
    case executingStep = "executing_step"
    case verificationFailed = "verification_failed"
    case completed
    case blocked
    case cancelled
    case error
    case thinking
    case acting
    case verifying
    case paused
    case unknown

    var id: String { rawValue }

    init(from decoder: Decoder) throws {
        let rawValue = try decoder.singleValueContainer().decode(String.self)
        self = CuePhase(rawValue: rawValue) ?? .unknown
    }
}

struct CueWorkflowStep: Codable, Equatable, Identifiable {
    let stepID: String
    let title: String
    let action: CueWorkflowAction
    let expectedOutcome: String
    let verificationCriteria: String?

    var id: String { stepID }

    enum CodingKeys: String, CodingKey {
        case stepID = "step_id"
        case title
        case action
        case expectedOutcome = "expected_outcome"
        case verificationCriteria = "verification_criteria"
    }
}

struct CueWorkflowPreviewResponse: Codable, Equatable {
    let session: CueSessionState

    init(session: CueSessionState) {
        self.session = session
    }

    init(from decoder: Decoder) throws {
        self.session = try CueSessionState(from: decoder)
    }

    func encode(to encoder: Encoder) throws {
        try session.encode(to: encoder)
    }
}

struct CueVerificationResult: Codable, Equatable {
    let status: String
    let reason: String
    let expected: String?
    let actual: String?
    let nextRecommendation: String?

    enum CodingKeys: String, CodingKey {
        case status
        case reason
        case expected
        case actual
        case nextRecommendation = "next_recommendation"
    }
}

struct CueSessionState: Codable, Equatable, Identifiable {
    let sessionID: String
    let phase: CuePhase
    let workflowPlan: CueWorkflowPlan?
    let currentStepID: String?
    let verifiedSteps: [String]
    let lastVerification: CueVerificationResult?
    let narration: CueNarration?
    let stateSummary: CueStateSummary?
    let focusStatus: CueFocusStatus?
    let risk: CueRiskSummary?
    let policyDecision: CuePolicyDecision?
    let confirmationPrompt: String?
    let timing: CueTiming?
    let auditSummary: [String]
    let auditEvents: [CueAuditEvent]

    var id: String { sessionID }

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case phase = "state"
        case workflowPlan = "workflow_plan"
        case currentStepID = "current_step_id"
        case verifiedSteps = "verified_steps"
        case lastVerification = "last_verification"
        case narration
        case stateSummary = "state_summary"
        case focusStatus = "focus"
        case risk
        case policyDecision = "policy_decision"
        case confirmationPrompt = "confirmation_prompt"
        case timing
        case auditSummary = "audit_summary"
        case auditEvents = "audit_events"
    }

    init(
        sessionID: String,
        phase: CuePhase,
        workflowPlan: CueWorkflowPlan? = nil,
        currentStepID: String? = nil,
        verifiedSteps: [String] = [],
        lastVerification: CueVerificationResult? = nil,
        narration: CueNarration? = nil,
        stateSummary: CueStateSummary? = nil,
        focusStatus: CueFocusStatus? = nil,
        risk: CueRiskSummary? = nil,
        policyDecision: CuePolicyDecision? = nil,
        confirmationPrompt: String? = nil,
        timing: CueTiming? = nil,
        auditSummary: [String] = [],
        auditEvents: [CueAuditEvent] = []
    ) {
        self.sessionID = sessionID
        self.phase = phase
        self.workflowPlan = workflowPlan
        self.currentStepID = currentStepID
        self.verifiedSteps = verifiedSteps
        self.lastVerification = lastVerification
        self.narration = narration
        self.stateSummary = stateSummary
        self.focusStatus = focusStatus
        self.risk = risk
        self.policyDecision = policyDecision
        self.confirmationPrompt = confirmationPrompt
        self.timing = timing
        self.auditSummary = auditSummary
        self.auditEvents = auditEvents
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sessionID = try container.decode(String.self, forKey: .sessionID)
        phase = try container.decodeIfPresent(CuePhase.self, forKey: .phase) ?? .unknown
        workflowPlan = try container.decodeIfPresent(CueWorkflowPlan.self, forKey: .workflowPlan)
        currentStepID = try container.decodeIfPresent(String.self, forKey: .currentStepID)
        verifiedSteps = try container.decodeIfPresent([String].self, forKey: .verifiedSteps) ?? []
        lastVerification = try container.decodeIfPresent(CueVerificationResult.self, forKey: .lastVerification)
        narration = try container.decodeIfPresent(CueNarration.self, forKey: .narration)
        stateSummary = try container.decodeIfPresent(CueStateSummary.self, forKey: .stateSummary)
        focusStatus = try container.decodeIfPresent(CueFocusStatus.self, forKey: .focusStatus)
        risk = try container.decodeIfPresent(CueRiskSummary.self, forKey: .risk)
        policyDecision = try container.decodeIfPresent(CuePolicyDecision.self, forKey: .policyDecision)
        confirmationPrompt = try container.decodeIfPresent(String.self, forKey: .confirmationPrompt)
        timing = try container.decodeIfPresent(CueTiming.self, forKey: .timing)
        auditSummary = try container.decodeIfPresent([String].self, forKey: .auditSummary) ?? []
        auditEvents = try container.decodeIfPresent([CueAuditEvent].self, forKey: .auditEvents) ?? []
    }
}

struct CuePolicyDecision: Codable, Equatable {
    let allowed: Bool
    let approvalTier: String
    let reason: String
    let requiresReviewerApproval: Bool
    let redactionApplied: Bool

    enum CodingKeys: String, CodingKey {
        case allowed
        case approvalTier = "approval_tier"
        case reason
        case requiresReviewerApproval = "requires_reviewer_approval"
        case redactionApplied = "redaction_applied"
    }
}

struct CueAuditEvent: Codable, Equatable, Identifiable {
    let timestamp: String
    let eventType: String
    let sessionID: String
    let workflowID: String
    let state: String
    let currentStepID: String?
    let approvalTier: String
    let policyReason: String
    let verificationStatus: String
    let summary: String

    var id: String {
        "\(timestamp)-\(eventType)-\(summary)"
    }

    enum CodingKeys: String, CodingKey {
        case timestamp
        case eventType = "event_type"
        case sessionID = "session_id"
        case workflowID = "workflow_id"
        case state
        case currentStepID = "current_step_id"
        case approvalTier = "approval_tier"
        case policyReason = "policy_reason"
        case verificationStatus = "verification_status"
        case summary
    }
}

struct CueFocusStatus: Codable, Equatable {
    let activeApp: String?
    let activeWindow: String?
    let focusedElement: CueFocusElement?
    let cursorPosition: CueCursorPosition?
    let sources: [String]

    enum CodingKeys: String, CodingKey {
        case activeApp = "active_app"
        case activeWindow = "active_window"
        case focusedElement = "focused_element"
        case cursorPosition = "cursor_position"
        case sources
    }

    init(
        activeApp: String? = nil,
        activeWindow: String? = nil,
        focusedElement: CueFocusElement? = nil,
        cursorPosition: CueCursorPosition? = nil,
        sources: [String] = []
    ) {
        self.activeApp = activeApp
        self.activeWindow = activeWindow
        self.focusedElement = focusedElement
        self.cursorPosition = cursorPosition
        self.sources = sources
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        activeApp = try container.decodeIfPresent(String.self, forKey: .activeApp)
        activeWindow = try container.decodeIfPresent(String.self, forKey: .activeWindow)
        focusedElement = try container.decodeIfPresent(CueFocusElement.self, forKey: .focusedElement)
        cursorPosition = try container.decodeIfPresent(CueCursorPosition.self, forKey: .cursorPosition)
        sources = try container.decodeIfPresent([String].self, forKey: .sources) ?? []
    }
}

struct CueHealthResponse: Codable, Equatable {
    let status: String
    let app: String
}

struct CueWorkflowPlan: Codable, Equatable {
    let workflowID: String?
    let narration: String
    let workflowRequired: Bool
    let workflowCategory: String
    let steps: [CueWorkflowStep]
    let riskLevel: String
    let approvalTier: String
    let confirmationPrompt: String
    let expectedOutcome: String
    let riskReasons: [String]
    let requiresReviewerApproval: Bool
    let redactionApplied: Bool
    let allowedByPolicy: Bool
    let policyReason: String
    let auditEventSummary: String

    enum CodingKeys: String, CodingKey {
        case workflowID = "workflow_id"
        case narration
        case workflowRequired = "workflow_required"
        case workflowCategory = "workflow_category"
        case steps
        case riskLevel = "risk_level"
        case approvalTier = "approval_tier"
        case confirmationPrompt = "confirmation_prompt"
        case expectedOutcome = "expected_outcome"
        case riskReasons = "risk_reasons"
        case requiresReviewerApproval = "requires_reviewer_approval"
        case redactionApplied = "redaction_applied"
        case allowedByPolicy = "allowed_by_policy"
        case policyReason = "policy_reason"
        case auditEventSummary = "audit_event_summary"
    }
}

struct CueWorkflowAction: Codable, Equatable {
    let actionType: String
    let payload: [String: CueJSONValue]
    let reason: String
    let expectedApp: String?
    let expectedWindow: String?
    let expectedFocus: String?
    let changesState: Bool

    enum CodingKeys: String, CodingKey {
        case actionType = "action_type"
        case payload
        case reason
        case expectedApp = "expected_app"
        case expectedWindow = "expected_window"
        case expectedFocus = "expected_focus"
        case changesState = "changes_state"
    }
}

struct CueNarration: Codable, Equatable {
    let summary: String
    let speakableText: String
    let redactionApplied: Bool

    enum CodingKeys: String, CodingKey {
        case summary
        case speakableText = "speakable_text"
        case redactionApplied = "redaction_applied"
    }
}

struct CueStateSummary: Codable, Equatable {
    let state: String
    let currentStepID: String?
    let verifiedSteps: [String]
    let activeApp: String?
    let activeWindow: String?
    let lastObservationSummary: String?

    enum CodingKeys: String, CodingKey {
        case state
        case currentStepID = "current_step_id"
        case verifiedSteps = "verified_steps"
        case activeApp = "active_app"
        case activeWindow = "active_window"
        case lastObservationSummary = "last_observation_summary"
    }
}

struct CueRiskSummary: Codable, Equatable {
    let level: String
    let approvalTier: String
    let riskReasons: [String]

    enum CodingKeys: String, CodingKey {
        case level
        case approvalTier = "approval_tier"
        case riskReasons = "risk_reasons"
    }
}

struct CueTiming: Codable, Equatable {
    let backendMS: Int?

    enum CodingKeys: String, CodingKey {
        case backendMS = "backend_ms"
    }
}

struct CueFocusElement: Codable, Equatable {
    let status: String?
    let role: String?
    let title: String?
    let value: String?
    let reason: String?
    let source: String?
}

struct CueCursorPosition: Codable, Equatable {
    let status: String?
    let x: Double?
    let y: Double?
    let reason: String?
    let source: String?
}

enum CueJSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: CueJSONValue])
    case array([CueJSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: CueJSONValue].self) {
            self = .object(value)
        } else {
            self = .array(try container.decode([CueJSONValue].self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }
}
