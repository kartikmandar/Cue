import SwiftUI

struct WorkflowStepView: View {
    let step: CueWorkflowStep
    let index: Int
    let isCurrent: Bool
    let isVerified: Bool
    let approvalTier: String
    let riskReasons: [String]

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(index)")
                .font(.headline.monospacedDigit())
                .frame(width: 30, height: 30)
                .background(stepTint.opacity(0.16), in: Circle())
                .foregroundStyle(stepTint)

            VStack(alignment: .leading, spacing: 7) {
                HStack(alignment: .firstTextBaseline) {
                    Text(step.title)
                        .font(.headline)
                    Spacer()
                    if isVerified {
                        Label("Verified", systemImage: "checkmark.circle")
                            .font(.caption)
                            .foregroundStyle(.green)
                    } else if isCurrent {
                        Label("Current", systemImage: "location.circle")
                            .font(.caption)
                            .foregroundStyle(Color.accentColor)
                    }
                }
                DetailRow(title: "Action", value: step.action.actionType)
                DetailRow(title: "Reason", value: step.action.reason)
                DetailRow(title: "Expected", value: step.expectedOutcome)
                if let criteria = step.verificationCriteria {
                    DetailRow(title: "Verify", value: criteria)
                }
                ApprovalTierView(tier: approvalTier, compact: false)
                if !riskReasons.isEmpty {
                    Text(riskReasons.joined(separator: "; "))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(12)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isCurrent ? Color.accentColor : Color.secondary.opacity(0.18), lineWidth: isCurrent ? 1.5 : 1)
        )
        .accessibilityElement(children: .combine)
    }

    private var stepTint: Color {
        if isVerified {
            return .green
        }
        if isCurrent {
            return Color.accentColor
        }
        return .secondary
    }
}

private struct DetailRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .frame(width: 64, alignment: .leading)
            Text(value)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
