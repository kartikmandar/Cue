import SwiftUI

struct WorkflowPlanView: View {
    let plan: CueWorkflowPlan?
    let currentStepID: String?
    let verifiedSteps: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Workflow Plan", systemImage: "list.number")
                    .font(.headline)
                Spacer()
                if let approvalTier = plan?.approvalTier {
                    ApprovalTierView(tier: approvalTier, compact: true)
                }
            }

            if let plan {
                Text(plan.narration)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                if !plan.riskReasons.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(plan.riskReasons, id: \.self) { reason in
                            Label(reason, systemImage: "exclamationmark.triangle")
                                .font(.caption)
                                .foregroundStyle(.orange)
                        }
                    }
                }
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(plan.steps.enumerated()), id: \.element.id) { index, step in
                        WorkflowStepView(
                            step: step,
                            index: index + 1,
                            isCurrent: currentStepID == step.stepID,
                            isVerified: verifiedSteps.contains(step.stepID),
                            approvalTier: plan.approvalTier,
                            riskReasons: plan.riskReasons
                        )
                    }
                }
            } else {
                Text("Preview a request to see the approved action plan before Cue changes anything.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }
}
