import SwiftUI

struct FocusStatusView: View {
    let focus: CueFocusStatus?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Focus", systemImage: "scope")
                .font(.headline)
            FocusLine(title: "App", value: focus?.activeApp ?? "Unknown")
            FocusLine(title: "Window", value: focus?.activeWindow ?? "Unknown")
            FocusLine(title: "Element", value: elementSummary)
            FocusLine(title: "Cursor", value: cursorSummary)
            FocusLine(title: "Source", value: sourceSummary)
        }
        .accessibilityElement(children: .contain)
    }

    private var elementSummary: String {
        guard let element = focus?.focusedElement else { return "Unknown" }
        return [
            element.status,
            element.role,
            element.title,
            element.value
        ]
        .compactMap { $0?.nilIfBlank }
        .joined(separator: " | ")
        .nilIfBlank ?? "Unknown"
    }

    private var cursorSummary: String {
        guard let cursor = focus?.cursorPosition else { return "Unknown" }
        if let x = cursor.x, let y = cursor.y {
            return "\(Int(x)), \(Int(y))"
        }
        return cursor.reason ?? cursor.status ?? "Unknown"
    }

    private var sourceSummary: String {
        guard let focus, !focus.sources.isEmpty else {
            return focus?.focusedElement?.source ?? focus?.cursorPosition?.source ?? "Unknown"
        }
        return focus.sources.joined(separator: ", ")
    }
}

private struct FocusLine: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
