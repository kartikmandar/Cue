import SwiftUI

struct ConfirmationView: View {
    let prompt: String?
    let approvalTier: String?
    let requiresReviewerApproval: Bool
    let approve: () -> Void
    let requestReviewer: () -> Void
    let cancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Confirmation", systemImage: "hand.tap")
                .font(.headline)

            Text(prompt ?? "Cue will ask here before it changes state.")
                .font(.callout)
                .foregroundStyle(prompt == nil ? .secondary : .primary)

            if let approvalTier {
                ApprovalTierView(tier: approvalTier, compact: false)
            }

            HStack(spacing: 10) {
                Button {
                    approve()
                } label: {
                    Label("Approve Workflow", systemImage: "checkmark.seal")
                }
                .buttonStyle(.borderedProminent)
                .disabled(prompt == nil || requiresReviewerApproval)

                if requiresReviewerApproval {
                    Button {
                        requestReviewer()
                    } label: {
                        Label("Request Reviewer", systemImage: "person.2.badge.key")
                    }
                }

                Button(role: .cancel) {
                    cancel()
                } label: {
                    Label("Cancel", systemImage: "xmark.circle")
                }
                .disabled(prompt == nil)
            }
        }
        .padding(16)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .contain)
    }
}
