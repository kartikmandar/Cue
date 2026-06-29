# Global Listen Now Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global listen-now path that lets Cue capture a spoken command without bringing Cue's window to the front.

**Architecture:** Keep the fix in the native Swift shell. The global shortcut and status-bar menu call a new `AppState.startGlobalVoiceCommandCapture()` method, which starts voice input through the existing `VoiceInputController` and submits through the existing chat flow. The backend remains unchanged because the focus fix comes from avoiding `NSApp.activate` before `/chat` observes the desktop.

**Tech Stack:** SwiftUI, AppKit `NSEvent` monitors, existing `VoiceInputController`, existing `BackendClientProtocol`, XCTest, Pixi `test-mac`.

## Global Constraints

- All implementation files live under `Cue/`.
- Use Pixi tasks for verification.
- Do not add passive background recording, wake-word detection, background screenshots, new backend observation APIs, or Cua Driver changes.
- The hidden listen-now path must not call `NSApp.activate` or `makeKeyAndOrderFront`.
- The existing "Open Cue" path must remain available for the full window.
- Keep tests local and fake-only; do not run live model, network, or Cua calls.

---

## File Structure

- Modify `apps/mac/CueApp/AppState.swift`: add the global listen-now state method and use the existing voice/chat submission flow.
- Modify `apps/mac/CueApp/HotKeyController.swift`: split hotkey callbacks so the global shortcut can trigger listen-now while still allowing local/open-window behavior when needed.
- Modify `apps/mac/CueApp/CueStatusBarController.swift`: add a "Listen Now" menu item wired to the same hidden capture path.
- Modify `apps/mac/CueApp/CueApp.swift`: wire the app delegate so the menu and global hotkey call the new hidden capture method; keep "Open Cue" activating the window.
- Modify `apps/mac/CueAppTests/AppStateConversationTests.swift`: add state-level TDD coverage for global listen-now.
- Modify or create controller tests in `apps/mac/CueAppTests`: add test coverage for hotkey callback routing and status-bar menu entries if the existing AppKit types allow direct construction under XCTest.

---

### Task 1: AppState Global Voice Capture

**Files:**
- Modify: `apps/mac/CueApp/AppState.swift`
- Modify: `apps/mac/CueAppTests/AppStateConversationTests.swift`

**Interfaces:**
- Consumes: `AppState.voiceInputController`, `AppState.prepareForVoiceCommandCapture()`, `AppState.sendVoiceCommandIfTranscriptReady(voiceState:)`
- Produces: `@MainActor func startGlobalVoiceCommandCapture()`

- [ ] **Step 1: Write the failing test**

Add this test to `apps/mac/CueAppTests/AppStateConversationTests.swift`:

```swift
@MainActor
func testGlobalListenNowClearsStaleTextAndStartsVoiceCapture() async {
    let voiceInputController = VoiceInputController()
    let appState = AppState(voiceInputController: voiceInputController)
    appState.inputMode = .text
    appState.commandText = "stale command"

    appState.startGlobalVoiceCommandCapture()

    XCTAssertEqual(appState.inputMode, .voice)
    XCTAssertEqual(appState.commandText, "")
    XCTAssertTrue(voiceInputController.isBusy)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run test-mac --only-testing:CueAppTests/AppStateConversationTests/testGlobalListenNowClearsStaleTextAndStartsVoiceCapture`

Expected: FAIL because `AppState` has no `startGlobalVoiceCommandCapture()` method.

- [ ] **Step 3: Write minimal implementation**

Add this method to `AppState` near `prepareForVoiceCommandCapture()`:

```swift
func startGlobalVoiceCommandCapture() {
    guard !phase.isBusy else { return }
    inputMode = .voice
    prepareForVoiceCommandCapture()
    voiceInputController.clearTranscript()
    commandText = ""
    voiceInputController.startListening()
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run test-mac --only-testing:CueAppTests/AppStateConversationTests/testGlobalListenNowClearsStaleTextAndStartsVoiceCapture`

Expected: PASS.

- [ ] **Step 5: Add busy-state regression test**

Add this test:

```swift
@MainActor
func testGlobalListenNowDoesNotStartWhileCommandIsBusy() async {
    let voiceInputController = VoiceInputController()
    let appState = AppState(voiceInputController: voiceInputController)
    appState.phase = .thinking
    appState.commandText = "keep me"

    appState.startGlobalVoiceCommandCapture()

    XCTAssertEqual(appState.commandText, "keep me")
    XCTAssertFalse(voiceInputController.isBusy)
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pixi run test-mac --only-testing:CueAppTests/AppStateConversationTests/testGlobalListenNowDoesNotStartWhileCommandIsBusy`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/mac/CueApp/AppState.swift apps/mac/CueAppTests/AppStateConversationTests.swift
git commit -m "feat: add global voice capture state"
```

---

### Task 2: Hotkey And Status Menu Routing

**Files:**
- Modify: `apps/mac/CueApp/HotKeyController.swift`
- Modify: `apps/mac/CueApp/CueStatusBarController.swift`
- Modify: `apps/mac/CueApp/CueApp.swift`
- Modify or create: `apps/mac/CueAppTests/HotKeyControllerTests.swift`
- Modify or create: `apps/mac/CueAppTests/StatusBarControllerTests.swift`

**Interfaces:**
- Consumes: `AppState.startGlobalVoiceCommandCapture()`
- Produces: `HotKeyController.start(openPalette:listenNow:)`, a "Listen Now" status-bar menu action, and app delegate wiring that does not activate Cue for the global listen-now path.

- [ ] **Step 1: Write the failing hotkey test**

Create `apps/mac/CueAppTests/HotKeyControllerTests.swift` with:

```swift
import AppKit
import XCTest
@testable import CueApp

@MainActor
final class HotKeyControllerTests: XCTestCase {
    func testGlobalCueHotKeyInvokesListenNowCallback() {
        var openedPalette = false
        var listenedNow = false
        let controller = HotKeyController()

        controller.handleCueHotKey(
            scope: .global,
            openPalette: { openedPalette = true },
            listenNow: { listenedNow = true }
        )

        XCTAssertFalse(openedPalette)
        XCTAssertTrue(listenedNow)
    }

    func testLocalCueHotKeyKeepsOpeningPalette() {
        var openedPalette = false
        var listenedNow = false
        let controller = HotKeyController()

        controller.handleCueHotKey(
            scope: .local,
            openPalette: { openedPalette = true },
            listenNow: { listenedNow = true }
        )

        XCTAssertTrue(openedPalette)
        XCTAssertFalse(listenedNow)
    }
}
```

- [ ] **Step 2: Run hotkey test to verify it fails**

Run: `pixi run test-mac --only-testing:CueAppTests/HotKeyControllerTests`

Expected: FAIL because `HotKeyController.HotKeyScope` and `handleCueHotKey(scope:openPalette:listenNow:)` do not exist.

- [ ] **Step 3: Implement hotkey routing**

Update `HotKeyController` with:

```swift
enum HotKeyScope {
    case local
    case global
}

func start(
    openPalette: @escaping @MainActor () -> Void,
    listenNow: @escaping @MainActor () -> Void
) {
    stop()

    localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
        guard Self.matchesCueHotKey(event) else { return event }
        self?.handleCueHotKey(scope: .local, openPalette: openPalette, listenNow: listenNow)
        return nil
    }

    globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
        guard Self.matchesCueHotKey(event) else { return }
        Task { @MainActor in
            self?.handleCueHotKey(scope: .global, openPalette: openPalette, listenNow: listenNow)
        }
    }
}

func handleCueHotKey(
    scope: HotKeyScope,
    openPalette: @escaping @MainActor () -> Void,
    listenNow: @escaping @MainActor () -> Void
) {
    switch scope {
    case .local:
        openPalette()
    case .global:
        listenNow()
    }
}
```

Keep `matchesCueHotKey(_:)` unchanged.

- [ ] **Step 4: Run hotkey test to verify it passes**

Run: `pixi run test-mac --only-testing:CueAppTests/HotKeyControllerTests`

Expected: PASS.

- [ ] **Step 5: Write the failing status-menu test**

Create `apps/mac/CueAppTests/StatusBarControllerTests.swift` with:

```swift
import XCTest
@testable import CueApp

@MainActor
final class StatusBarControllerTests: XCTestCase {
    func testStatusMenuContainsListenNowAndOpenCue() {
        let appState = AppState()
        let controller = CueStatusBarController(
            appState: appState,
            listenNow: {},
            openCue: {},
            quitCue: {}
        )

        let titles = controller.menuItemTitlesForTesting()

        XCTAssertTrue(titles.contains("Listen Now"))
        XCTAssertTrue(titles.contains("Open Cue"))
        XCTAssertLessThan(
            titles.firstIndex(of: "Listen Now")!,
            titles.firstIndex(of: "Open Cue")!
        )
    }
}
```

- [ ] **Step 6: Run status-menu test to verify it fails**

Run: `pixi run test-mac --only-testing:CueAppTests/StatusBarControllerTests`

Expected: FAIL because `CueStatusBarController` does not accept `listenNow` and has no testing menu-title accessor.

- [ ] **Step 7: Implement status menu routing**

Update `CueStatusBarController`:

```swift
private let listenNow: () -> Void
private let openCue: () -> Void
private let quitCue: () -> Void

init(
    appState: AppState,
    listenNow: @escaping () -> Void,
    openCue: @escaping () -> Void,
    quitCue: @escaping () -> Void
) {
    self.statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    self.appState = appState
    self.listenNow = listenNow
    self.openCue = openCue
    self.quitCue = quitCue
    super.init()
    configure()
}
```

In `rebuildMenu()`, add the listen item before open:

```swift
menu.addItem(NSMenuItem(title: "Listen Now", action: #selector(listenNowAction), keyEquivalent: ""))
menu.addItem(NSMenuItem(title: "Open Cue", action: #selector(openCueAction), keyEquivalent: "o"))
```

Add:

```swift
func menuItemTitlesForTesting() -> [String] {
    statusItem.menu?.items.map(\.title) ?? []
}

@objc private func listenNowAction() {
    listenNow()
}
```

- [ ] **Step 8: Wire app delegate without activating Cue for listen-now**

Update `CueAppDelegate.configure(appState:)`:

```swift
let listenNow: @MainActor () -> Void = { [weak appState] in
    appState?.startGlobalVoiceCommandCapture()
}
let openCue: @MainActor () -> Void = {
    NSApp.activate(ignoringOtherApps: true)
    NSApp.windows.first?.makeKeyAndOrderFront(nil)
}

statusBarController = CueStatusBarController(
    appState: appState,
    listenNow: listenNow,
    openCue: openCue,
    quitCue: {
        NSApp.terminate(nil)
    }
)
hotKeyController = HotKeyController()
hotKeyController?.start(openPalette: openCue, listenNow: listenNow)
```

- [ ] **Step 9: Run controller tests**

Run: `pixi run test-mac --only-testing:CueAppTests/HotKeyControllerTests --only-testing:CueAppTests/StatusBarControllerTests`

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add apps/mac/CueApp/HotKeyController.swift apps/mac/CueApp/CueStatusBarController.swift apps/mac/CueApp/CueApp.swift apps/mac/CueAppTests/HotKeyControllerTests.swift apps/mac/CueAppTests/StatusBarControllerTests.swift
git commit -m "feat: route global hotkey to listen now"
```

---

### Task 3: Full Verification And Polish

**Files:**
- Modify only if tests reveal a compile issue: Swift files touched in Tasks 1 and 2.

**Interfaces:**
- Consumes: All interfaces from Tasks 1 and 2.
- Produces: A passing local test suite and a clean git state.

- [ ] **Step 1: Run full Swift verification**

Run: `pixi run test-mac`

Expected: PASS.

- [ ] **Step 2: Inspect for forbidden focus activation in listen-now path**

Run: `rg -n "startGlobalVoiceCommandCapture|activate\\(|makeKeyAndOrderFront|listenNow" apps/mac/CueApp`

Expected: `startGlobalVoiceCommandCapture` and `listenNow` references do not call `NSApp.activate` or `makeKeyAndOrderFront`; only the `openCue` path calls them.

- [ ] **Step 3: Run Python tests only if backend files changed**

If no Python files changed, skip this step and record that backend tests were not needed. If Python files changed, run: `pixi run test`

Expected: PASS.

- [ ] **Step 4: Commit any verification polish**

If Step 1 or Step 2 required fixes:

```bash
git add apps/mac/CueApp apps/mac/CueAppTests
git commit -m "fix: polish global listen now verification"
```

If no fixes were needed, make no commit.
