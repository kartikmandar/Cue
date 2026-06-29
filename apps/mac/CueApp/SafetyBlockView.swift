import SwiftUI

struct SafetyBlockView: View {
    let session: CueSessionState?
    let phase: CuePhase

    var body: some View {
        Group {
            if let message {
                Label(message, systemImage: "hand.raised.fill")
                    .font(.callout.weight(.medium))
                    .foregroundStyle(.red)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red.opacity(0.10), in: RoundedRectangle(cornerRadius: 8))
                    .accessibilityLabel("Safety block: \(message)")
            }
        }
    }

    private var message: String? {
        if phase == .blocked {
            return session?.policyDecision?.reason
                ?? session?.workflowPlan?.policyReason
                ?? "Cue blocked this workflow for safety."
        }
        if session?.policyDecision?.allowed == false {
            return session?.policyDecision?.reason ?? "Cue policy does not allow this action."
        }
        if session?.workflowPlan?.allowedByPolicy == false {
            return session?.workflowPlan?.policyReason ?? "Cue policy does not allow this workflow."
        }
        return nil
    }
}
