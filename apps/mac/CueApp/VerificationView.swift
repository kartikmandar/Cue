import SwiftUI

struct VerificationView: View {
    let result: CueVerificationResult?
    let phase: CuePhase
    let reobserve: () -> Void
    let revisePlan: () -> Void
    let cancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Verification", systemImage: "checklist.checked")
                    .font(.headline)
                Spacer()
                if let result {
                    Text(result.status.capitalized)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(statusColor)
                }
            }

            if let result {
                Text(result.reason)
                    .font(.callout)
                if let expected = result.expected {
                    VerificationLine(title: "Expected", value: expected)
                }
                if let actual = result.actual {
                    VerificationLine(title: "Actual", value: actual)
                }
                if let next = result.nextRecommendation {
                    VerificationLine(title: "Next", value: next)
                }
            } else {
                Text("Cue verifies each executed step before continuing.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            if phase == .verificationFailed || result?.status.lowercased() == "failed" {
                HStack(spacing: 10) {
                    Button {
                        reobserve()
                    } label: {
                        Label("Re-observe", systemImage: "eye")
                    }
                    Button {
                        revisePlan()
                    } label: {
                        Label("Revise Plan", systemImage: "arrow.triangle.branch")
                    }
                    Button(role: .cancel) {
                        cancel()
                    } label: {
                        Label("Cancel", systemImage: "xmark.circle")
                    }
                }
            }
        }
        .padding(16)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }

    private var statusColor: Color {
        switch result?.status.lowercased() {
        case "passed", "pass", "verified":
            .green
        case "failed", "fail":
            .red
        case "uncertain":
            .orange
        default:
            .secondary
        }
    }
}

private struct VerificationLine: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.callout)
        }
    }
}
