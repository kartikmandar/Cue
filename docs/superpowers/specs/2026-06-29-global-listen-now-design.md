# Global Listen Now Design

## Problem

When the user asks Cue what is happening on screen from inside the Cue window, Cue observes itself because the native app activates and becomes frontmost before the backend observes the desktop. This breaks the core blind-first workflow: the user should be able to keep Chrome, Terminal, VS Code, Preview, or another app frontmost and ask Cue what is happening there.

## Goal

Add a global "listen now" path that lets the user invoke Cue system-wide without bringing the Cue window to the front. The default global trigger should keep the current application frontmost, capture a short spoken request, send it to the existing chat endpoint, and speak the response.

## User Flow

1. User is working in another app.
2. User presses the global Cue shortcut or chooses a status-bar "Listen Now" action.
3. Cue starts voice capture without activating its main window.
4. User asks a command such as "tell me what is happening on my screen."
5. Cue stops capture, submits the transcript through the existing chat flow, and the backend observes the current frontmost app.
6. Cue speaks the response. The main Cue window remains hidden unless the user explicitly opens it.

## Architecture

The Swift app owns invocation and voice capture. The existing `HotKeyController` should support a second callback for background listen-now behavior rather than always opening the command palette. `CueStatusBarController` should expose a matching menu item so mouse users can trigger the same path without opening the app.

`AppState` should own a single method for starting the global voice command capture. That method should clear the current transcript, prepare auto-submit de-duplication, switch to voice mode if needed, and start `VoiceInputController` listening. It should not call `NSApp.activate` and should not call `makeKeyAndOrderFront`.

The existing `sendVoiceCommandIfTranscriptReady` and `sendChatCommand` path should remain the submission path. This keeps conversation state, narration, backend responses, and tests concentrated in one place.

The Python backend should not need a new observation implementation for the initial fix. The important behavior is that the frontend does not steal focus before `/chat` calls `observe_desktop`.

## UI And State

The default shortcut behavior is background capture. "Open Cue" remains available from the status-bar menu for users who want the full palette and inspector. Visible feedback beyond existing speech and app-state updates is outside this first fix.

The menu should distinguish:

- "Listen Now" for background voice capture.
- "Open Cue" for showing the full window.

## Error Handling

If voice input permission is unavailable, Cue should not silently open the main window. It should set an error message in app state and speak a short failure if speech is enabled.

If the backend is unavailable, the existing chat error handling should remain responsible for the user-facing message.

If a command is already running, listen-now should not start a second command. It should preserve the current busy-state guard.

## Testing

Add Swift tests for the state-level behavior:

- Global listen-now prepares voice capture, clears stale command text, and starts listening.
- Global listen-now does not submit duplicate transcripts within one capture.
- Busy phases do not start overlapping command capture.

Add controller-level tests for the non-UI logic:

- The global hotkey invokes the listen-now callback instead of the open-window callback for the global background path.
- The status-bar menu contains both "Listen Now" and "Open Cue".

Run the repo's local verification gates after implementation:

- `pixi run test-mac`
- Targeted Python tests only if the backend request contract changes.

## Out Of Scope

- Passive background recording.
- Continuous wake-word detection.
- Background screenshot capture.
- New backend observation APIs.
- A visible non-activating overlay.
- Changing Cua Driver behavior.
