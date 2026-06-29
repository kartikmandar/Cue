import AppKit

@MainActor
final class CueStatusBarController: NSObject {
    private let statusItem: NSStatusItem
    private weak var appState: AppState?
    private let openCue: () -> Void
    private let quitCue: () -> Void

    init(
        appState: AppState,
        openCue: @escaping () -> Void,
        quitCue: @escaping () -> Void
    ) {
        self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        self.appState = appState
        self.openCue = openCue
        self.quitCue = quitCue
        super.init()
        configure()
    }

    private func configure() {
        statusItem.button?.title = "Cue"
        statusItem.button?.setAccessibilityLabel("Cue status menu")
        rebuildMenu()
    }

    func rebuildMenu() {
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Cue", action: #selector(openCueAction), keyEquivalent: "o"))
        menu.addItem(NSMenuItem(title: "Pause Cue", action: #selector(pauseCueAction), keyEquivalent: "p"))
        menu.addItem(NSMenuItem(title: privacyStatusTitle(), action: #selector(privacyStatusAction), keyEquivalent: ""))
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quitCueAction), keyEquivalent: "q"))
        for item in menu.items {
            item.target = self
        }
        statusItem.menu = menu
    }

    private func privacyStatusTitle() -> String {
        guard let appState else {
            return "Privacy Status: Unknown"
        }
        let mode = appState.privacyMode.capitalized
        let audit = appState.onboardingStatus.auditRedactionEnabled ? "Audit Redacted" : "Audit Raw"
        return "Privacy Status: \(mode), \(audit)"
    }

    @objc private func openCueAction() {
        openCue()
    }

    @objc private func pauseCueAction() {
        appState?.pauseCue()
        rebuildMenu()
    }

    @objc private func privacyStatusAction() {
        appState?.refreshLocalStatus()
        rebuildMenu()
    }

    @objc private func quitCueAction() {
        quitCue()
    }
}
