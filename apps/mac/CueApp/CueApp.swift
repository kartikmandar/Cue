import SwiftUI

@main
struct CueApp: App {
    @NSApplicationDelegateAdaptor(CueAppDelegate.self) private var appDelegate
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup("Cue") {
            OnboardingView()
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
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
