import SwiftUI

@main
struct CueApp: App {
    @NSApplicationDelegateAdaptor(CueAppDelegate.self) private var appDelegate
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup("Cue") {
            CommandPaletteView()
                .environmentObject(appState)
                .onAppear {
                    appDelegate.configure(appState: appState)
                }
        }
    }
}

@MainActor
final class CueAppDelegate: NSObject, NSApplicationDelegate {
    private var statusBarController: CueStatusBarController?
    private var hotKeyController: HotKeyController?

    func configure(appState: AppState) {
        guard statusBarController == nil else { return }
        statusBarController = CueStatusBarController(
            appState: appState,
            openCue: {
                NSApp.activate(ignoringOtherApps: true)
                NSApp.windows.first?.makeKeyAndOrderFront(nil)
            },
            quitCue: {
                NSApp.terminate(nil)
            }
        )
        hotKeyController = HotKeyController()
        hotKeyController?.start {
            NSApp.activate(ignoringOtherApps: true)
            NSApp.windows.first?.makeKeyAndOrderFront(nil)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
