import AppKit
import ApplicationServices
import Combine
import CoreGraphics
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var phase: CuePhase = .idle
    @Published var commandText = ""
    @Published var inputMode: CueInputMode = .text
    @Published var backendHealth: BackendHealth = .unknown
    @Published var currentSession: CueSessionState?
    @Published var lastResponse: CueWorkflowPreviewResponse?
    @Published var speechEnabled = true
    @Published var privacyMode = "strict"
    @Published var pendingApproval = false
    @Published var focusStatus: CueFocusStatus?
    @Published var auditSummary: [String] = []
    @Published var onboardingStatus = CueOnboardingStatus.defaults
    @Published var lastErrorMessage: String?

    private let backendClient: BackendClient

    init(backendClient: BackendClient = BackendClient()) {
        self.backendClient = backendClient
        refreshLocalStatus()
    }

    func refreshLocalStatus() {
        let environment = ProcessInfo.processInfo.environment
        privacyMode = environment["CUE_PRIVACY_MODE", default: "strict"]
        speechEnabled = environment["CUE_SPEAK"].map { $0 != "false" } ?? true
        onboardingStatus = CueOnboardingStatus(
            cuaStatus: Self.cuaStatus(),
            accessibilityPermission: AXIsProcessTrusted() ? .ready : .needsPermission,
            screenRecordingPermission: CGPreflightScreenCaptureAccess() ? .ready : .needsPermission,
            cerebrasAPIKeyStatus: environment["CEREBRAS_API_KEY"].isNilOrEmpty ? .missing : .ready,
            strictPrivacyMode: privacyMode.caseInsensitiveCompare("strict") == .orderedSame,
            auditRedactionEnabled: environment["CUE_AUDIT_LOG_REDACTED"].map { $0 != "false" } ?? true,
            terminalWriteDisabled: environment["CUE_ALLOW_TERMINAL_WRITE"].map { $0 != "true" } ?? true,
            reviewerModeEnabled: environment["CUE_REVIEWER_MODE"].map { $0 == "true" } ?? false
        )
    }

    func refreshBackendHealth() async {
        do {
            let response = try await backendClient.health()
            backendHealth = response.status == "ok" ? .healthy : .unavailable
            lastErrorMessage = nil
        } catch {
            backendHealth = .unavailable
            lastErrorMessage = error.localizedDescription
        }
    }

    func previewCommand() async {
        let command = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else {
            lastErrorMessage = "Enter a Cue command first."
            return
        }
        phase = .thinking
        do {
            let response = try await backendClient.preview(command: command)
            lastResponse = response
            apply(response.session)
            lastErrorMessage = nil
        } catch {
            phase = .error
            lastErrorMessage = error.localizedDescription
        }
    }

    func approveWorkflow() async {
        guard let sessionID = currentSession?.sessionID else { return }
        await updateSession {
            try await backendClient.approve(sessionID: sessionID)
        }
    }

    func executeNextStep() async {
        guard let sessionID = currentSession?.sessionID else { return }
        phase = .acting
        await updateSession {
            try await backendClient.next(sessionID: sessionID)
        }
    }

    func cancelWorkflow() async {
        guard let sessionID = currentSession?.sessionID else { return }
        await updateSession {
            try await backendClient.cancel(sessionID: sessionID)
        }
    }

    func pauseCue() {
        pendingApproval = false
        phase = .paused
    }

    func apply(_ session: CueSessionState) {
        currentSession = session
        phase = session.phase
        pendingApproval = session.phase == .awaitingWorkflowApproval
            || session.phase == .awaitingStepApproval
            || session.phase == .awaitingReviewerApproval
        focusStatus = session.focusStatus
        auditSummary = session.auditSummary
    }

    private func updateSession(_ operation: () async throws -> CueSessionState) async {
        do {
            let session = try await operation()
            apply(session)
            lastErrorMessage = nil
        } catch {
            phase = .error
            lastErrorMessage = error.localizedDescription
        }
    }

    private static func cuaStatus() -> LocalStatus {
        if FileManager.default.fileExists(atPath: "/Applications/Cua.app") {
            return .ready
        }
        if NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.trycua.Cua") != nil {
            return .ready
        }
        return .missing
    }
}

enum CueInputMode: String, CaseIterable, Identifiable {
    case text
    case voice

    var id: String { rawValue }
}

enum BackendHealth: String {
    case unknown
    case healthy
    case unavailable
}

enum LocalStatus: String {
    case ready
    case missing
    case needsPermission

    var label: String {
        switch self {
        case .ready:
            "Ready"
        case .missing:
            "Missing"
        case .needsPermission:
            "Needs Permission"
        }
    }
}

struct CueOnboardingStatus: Equatable {
    let cuaStatus: LocalStatus
    let accessibilityPermission: LocalStatus
    let screenRecordingPermission: LocalStatus
    let cerebrasAPIKeyStatus: LocalStatus
    let strictPrivacyMode: Bool
    let auditRedactionEnabled: Bool
    let terminalWriteDisabled: Bool
    let reviewerModeEnabled: Bool

    static let defaults = CueOnboardingStatus(
        cuaStatus: .missing,
        accessibilityPermission: .needsPermission,
        screenRecordingPermission: .needsPermission,
        cerebrasAPIKeyStatus: .missing,
        strictPrivacyMode: true,
        auditRedactionEnabled: true,
        terminalWriteDisabled: true,
        reviewerModeEnabled: false
    )
}

private extension Optional where Wrapped == String {
    var isNilOrEmpty: Bool {
        switch self {
        case .none:
            true
        case .some(let value):
            value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }
}
