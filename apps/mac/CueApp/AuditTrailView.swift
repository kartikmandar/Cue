import SwiftUI

struct AuditTrailView: View {
    let events: [CueAuditEvent]
    let summary: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Audit", systemImage: "doc.text.magnifyingglass")
                .font(.headline)
            if !events.isEmpty {
                ForEach(events.prefix(6)) { event in
                    AuditLine(title: event.eventType, value: event.summary)
                }
            } else if !summary.isEmpty {
                ForEach(Array(summary.prefix(6).enumerated()), id: \.offset) { _, item in
                    AuditLine(title: "Current Session", value: item)
                }
            } else {
                Text("No redacted events for this session yet.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .contain)
    }
}

private struct AuditLine: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title.replacingOccurrences(of: "_", with: " ").capitalized)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
