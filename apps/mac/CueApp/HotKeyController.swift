import AppKit
import Foundation

@MainActor
final class HotKeyController {
    private var localMonitor: Any?
    private var globalMonitor: Any?

    func start(openPalette: @escaping @MainActor () -> Void) {
        stop()

        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            guard Self.matchesCueHotKey(event) else { return event }
            openPalette()
            return nil
        }

        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { event in
            guard Self.matchesCueHotKey(event) else { return }
            Task { @MainActor in
                openPalette()
            }
        }
    }

    func stop() {
        if let localMonitor {
            NSEvent.removeMonitor(localMonitor)
            self.localMonitor = nil
        }
        if let globalMonitor {
            NSEvent.removeMonitor(globalMonitor)
            self.globalMonitor = nil
        }
    }

    private static func matchesCueHotKey(_ event: NSEvent) -> Bool {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        return event.keyCode == 49
            && flags.contains(.command)
            && flags.contains(.shift)
            && !flags.contains(.option)
            && !flags.contains(.control)
    }
}
