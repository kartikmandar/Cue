import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

struct PermissionChecker {
    private let environment: [String: String]
    private let fileExists: (String) -> Bool
    private let applicationURLForBundleIdentifier: (String) -> URL?
    private let isAccessibilityTrusted: () -> Bool
    private let canRecordScreen: () -> Bool

    init(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        fileExists: @escaping (String) -> Bool = { FileManager.default.fileExists(atPath: $0) },
        applicationURLForBundleIdentifier: @escaping (String) -> URL? = {
            NSWorkspace.shared.urlForApplication(withBundleIdentifier: $0)
        },
        isAccessibilityTrusted: @escaping () -> Bool = { AXIsProcessTrusted() },
        canRecordScreen: @escaping () -> Bool = { CGPreflightScreenCaptureAccess() }
    ) {
        self.environment = environment
        self.fileExists = fileExists
        self.applicationURLForBundleIdentifier = applicationURLForBundleIdentifier
        self.isAccessibilityTrusted = isAccessibilityTrusted
        self.canRecordScreen = canRecordScreen
    }

    func snapshot() -> CueOnboardingStatus {
        CueOnboardingStatus(
            cuaStatus: cuaStatus(),
            accessibilityPermission: isAccessibilityTrusted() ? .ready : .needsPermission,
            screenRecordingPermission: canRecordScreen() ? .ready : .needsPermission,
            cerebrasAPIKeyStatus: environment["CEREBRAS_API_KEY"].isNilOrEmpty ? .missing : .ready,
            strictPrivacyMode: environment["CUE_PRIVACY_MODE", default: "strict"]
                .caseInsensitiveCompare("strict") == .orderedSame,
            auditRedactionEnabled: environment["CUE_AUDIT_LOG_REDACTED"].map { $0 != "false" } ?? true,
            terminalWriteDisabled: environment["CUE_ALLOW_TERMINAL_WRITE"].map { $0 != "true" } ?? true,
            reviewerModeEnabled: environment["CUE_REVIEWER_MODE"].map { $0 == "true" } ?? false
        )
    }

    private func cuaStatus() -> LocalStatus {
        if fileExists("/Applications/Cua.app") {
            return .ready
        }
        if applicationURLForBundleIdentifier("com.trycua.Cua") != nil {
            return .ready
        }
        return .missing
    }
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
