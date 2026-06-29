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

@MainActor
final class PushToTalkShortcutController {
    static let spaceKeyCode: UInt16 = 49

    private let isEnabled: () -> Bool
    private let startListening: () -> Void
    private let stopListening: () -> Void
    private var localMonitor: Any?
    private var isPressed = false

    init(
        isEnabled: @escaping () -> Bool,
        startListening: @escaping () -> Void,
        stopListening: @escaping () -> Void
    ) {
        self.isEnabled = isEnabled
        self.startListening = startListening
        self.stopListening = stopListening
    }

    func start() {
        stop()
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .keyUp]) { [weak self] event in
            guard let self else { return event }
            return self.handle(event) ? nil : event
        }
    }

    func stop() {
        if let localMonitor {
            NSEvent.removeMonitor(localMonitor)
            self.localMonitor = nil
        }
        release()
    }

    @discardableResult
    func handle(_ event: NSEvent) -> Bool {
        handleKeyEvent(
            type: event.type,
            keyCode: event.keyCode,
            modifierFlags: event.modifierFlags,
            isRepeat: event.isARepeat
        )
    }

    @discardableResult
    func handleKeyEvent(
        type: NSEvent.EventType,
        keyCode: UInt16,
        modifierFlags: NSEvent.ModifierFlags,
        isRepeat: Bool
    ) -> Bool {
        guard keyCode == Self.spaceKeyCode else { return false }

        if type == .keyUp, isPressed {
            release()
            return true
        }

        guard isEnabled(), !hasCommandModifiers(modifierFlags) else { return false }

        switch type {
        case .keyDown:
            if !isRepeat {
                press()
            }
            return true
        case .keyUp:
            release()
            return true
        default:
            return false
        }
    }

    func press() {
        guard !isPressed else { return }
        isPressed = true
        startListening()
    }

    func release() {
        guard isPressed else { return }
        isPressed = false
        stopListening()
    }

    private func hasCommandModifiers(_ modifierFlags: NSEvent.ModifierFlags) -> Bool {
        let flags = modifierFlags.intersection(.deviceIndependentFlagsMask)
        return flags.contains(.command)
            || flags.contains(.shift)
            || flags.contains(.option)
            || flags.contains(.control)
    }
}
