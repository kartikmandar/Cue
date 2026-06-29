import XCTest
@testable import CueApp

final class PermissionCheckerTests: XCTestCase {
    func testSnapshotUsesInjectedEnvironmentWithoutPrompting() {
        let checker = PermissionChecker(
            environment: [
                "CEREBRAS_API_KEY": "test-key",
                "CUE_PRIVACY_MODE": "strict",
                "CUE_AUDIT_LOG_REDACTED": "true",
                "CUE_ALLOW_TERMINAL_WRITE": "false",
                "CUE_REVIEWER_MODE": "true"
            ],
            fileExists: { path in path == "/Applications/Cua.app" },
            applicationURLForBundleIdentifier: { _ in nil },
            isAccessibilityTrusted: { true },
            canRecordScreen: { false },
            microphonePermission: { .ready },
            speechRecognitionPermission: { .needsPermission }
        )

        let status = checker.snapshot()

        XCTAssertEqual(status.cuaStatus, .ready)
        XCTAssertEqual(status.accessibilityPermission, .ready)
        XCTAssertEqual(status.screenRecordingPermission, .needsPermission)
        XCTAssertEqual(status.microphonePermission, .ready)
        XCTAssertEqual(status.speechRecognitionPermission, .needsPermission)
        XCTAssertEqual(status.cerebrasAPIKeyStatus, .ready)
        XCTAssertTrue(status.strictPrivacyMode)
        XCTAssertTrue(status.auditRedactionEnabled)
        XCTAssertTrue(status.terminalWriteDisabled)
        XCTAssertTrue(status.reviewerModeEnabled)
    }

    func testSnapshotRecognizesInstalledCuaDriverAppBundle() {
        let checker = PermissionChecker(
            environment: [:],
            fileExists: { path in path == "/Applications/CuaDriver.app" },
            applicationURLForBundleIdentifier: { _ in nil },
            isAccessibilityTrusted: { true },
            canRecordScreen: { true },
            microphonePermission: { .ready },
            speechRecognitionPermission: { .ready }
        )

        let status = checker.snapshot()

        XCTAssertEqual(status.cuaStatus, .ready)
    }
}
