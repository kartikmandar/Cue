import SwiftUI

struct ApprovalTierView: View {
    let tier: String
    let compact: Bool

    var body: some View {
        Label(label, systemImage: iconName)
            .font(compact ? .caption.weight(.semibold) : .callout.weight(.semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, compact ? 8 : 10)
            .padding(.vertical, compact ? 4 : 6)
            .background(tint.opacity(0.12), in: Capsule())
            .accessibilityLabel("Approval tier \(label)")
    }

    private var label: String {
        tier.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private var iconName: String {
        switch tier {
        case "inform_only":
            "info.circle"
        case "confirm_each_action":
            "checkmark.circle"
        case "confirm_sensitive":
            "exclamationmark.triangle"
        case "guardian_required":
            "person.2.badge.key"
        case "blocked":
            "hand.raised"
        default:
            "questionmark.circle"
        }
    }

    private var tint: Color {
        switch tier {
        case "inform_only":
            .blue
        case "confirm_each_action":
            .green
        case "confirm_sensitive":
            .orange
        case "guardian_required":
            .purple
        case "blocked":
            .red
        default:
            .secondary
        }
    }
}
