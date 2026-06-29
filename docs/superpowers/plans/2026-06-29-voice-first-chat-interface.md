# Voice-First Chat Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Cue's default macOS experience as a voice-first conversational assistant that can still preview, approve, execute, verify, narrate, and expose technical details on demand.

**Architecture:** Keep the existing Python backend session/orchestrator as the action engine, but add a chat endpoint that routes casual/conversational messages separately from actionable workflow previews. Replace the main SwiftUI surface with a conversation transcript, voice-first composer, inline action cards, and a collapsible details inspector. Add a real macOS speech-recognition controller so voice input is an implemented path rather than a selector.

**Tech Stack:** SwiftUI/AppKit, AVFoundation, Speech.framework, FastAPI, Pydantic, existing Cua Driver adapter, Pixi-only test/build/run commands.

## Global Constraints

- All implementation files live under `Cue/`; the outer repo remains planning/reference only.
- Use Pixi for every Python test/build/run command.
- Keep state-changing desktop actions behind explicit approval.
- Voice is the default input mode; text remains a fallback.
- Do not enable always-on listening by default.
- Keep raw workflow/policy/audit/focus details available, but hidden behind an inspector by default.
- Preserve strict privacy defaults: no screenshot persistence, redacted audit, terminal write disabled.

---

### Task 1: Backend Chat Routing

**Files:**
- Create: `tests/test_chat.py`
- Create: `cue/chat.py`
- Modify: `cue/backend.py`
- Modify: `cue/api.py`
- Modify: `pixi.toml`

**Interfaces:**
- Produces: `CueBackend.chat(request: str, conversation_id: str | None = None) -> dict[str, Any]`
- Produces: `POST /chat` with request body `{ "request": "...", "conversation_id": "optional" }`
- Produces response keys: `conversation_id`, `assistant_message`, `mode`, `session`, `suggested_replies`

- [x] Write failing backend/API tests for casual chat, capability help, action routing, and empty requests.
- [x] Run `pixi run test-chat` and confirm failure before implementation.
- [x] Implement `cue/chat.py` with deterministic routing and conversational responses.
- [x] Wire `CueBackend.chat` and `POST /chat`.
- [x] Add `test-chat` task.
- [x] Run `pixi run test-chat` and `pixi run test-api`.
- [x] Commit backend chat slice.

### Task 2: Swift Chat Models And Client

**Files:**
- Modify: `apps/mac/CueApp/Models.swift`
- Modify: `apps/mac/CueApp/BackendClient.swift`
- Modify: `apps/mac/CueAppTests/BackendClientTests.swift`

**Interfaces:**
- Produces: `CueChatMessage`, `CueChatRole`, `CueChatResponse`, and `BackendClient.chat(command:conversationID:)`.
- Consumes: `POST /chat` backend response from Task 1.

- [x] Write failing XCTest for `BackendClient.chat` request body and response decoding.
- [x] Run `pixi run test-mac` and confirm failure.
- [x] Add chat response models and client method.
- [x] Run `pixi run test-mac`.
- [x] Commit Swift client/model slice.

### Task 3: Voice Input Controller

**Files:**
- Create: `apps/mac/CueApp/VoiceInputController.swift`
- Create: `apps/mac/CueAppTests/VoiceInputControllerTests.swift`
- Modify: `apps/mac/CueApp/PermissionChecker.swift`
- Modify: `apps/mac/CueApp/AppState.swift`
- Modify: `apps/mac/CueApp/CueApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces: `VoiceInputController` with states `idle`, `requestingPermission`, `listening`, `transcribing`, `unavailable`, `error`.
- Produces: `startListening()`, `stopListening()`, `cancelListening()`, and transcript callbacks.
- Adds microphone/speech-recognition status to onboarding/local status.

- [x] Write failing XCTest for permission/status mapping and default voice state.
- [x] Run `pixi run test-mac` and confirm failure.
- [x] Implement controller with Speech.framework and AVAudioEngine.
- [x] Wire controller into `AppState`.
- [x] Run `pixi run test-mac`.
- [x] Commit voice controller slice.

### Task 4: Voice-First Conversation UI

**Files:**
- Create: `apps/mac/CueApp/ConversationView.swift`
- Create: `apps/mac/CueApp/ConversationModels.swift`
- Create: `apps/mac/CueApp/DetailsInspectorView.swift`
- Modify: `apps/mac/CueApp/CommandPaletteView.swift`
- Modify: `apps/mac/CueApp/AppState.swift`
- Modify: `apps/mac/CueApp/CueApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces: conversation transcript as the default screen.
- Produces: large mic-first composer with `Send`, `Push to Talk`, `Type instead`, and `Details`.
- Keeps workflow approval/execution controls as inline action cards.

- [x] Write failing UI-adjacent model tests where possible for default voice mode, message append behavior, and action-card state.
- [x] Run `pixi run test-mac` and confirm failure.
- [x] Implement conversation state and chat send flow.
- [x] Replace the default command palette body with conversation UI.
- [x] Move workflow/focus/privacy/audit/timing into a collapsible inspector.
- [x] Run `pixi run test-mac`.
- [x] Commit conversation UI slice.

### Task 5: End-To-End Verification And Packaging

**Files:**
- Modify: `README.md`

**Interfaces:**
- Updates user-facing run/use instructions to describe voice-first chat, typed fallback, action approvals, and details inspector.

- [x] Update README with the new interaction model and voice permission notes.
- [x] Run `pixi run test`.
- [x] Run `pixi run test-mac`.
- [x] Run `pixi run package`.
- [x] Run a read-only CLI/API smoke if backend changes warrant it.
- [x] Inspect `git status`.
- [x] Commit final docs/packaging slice.
- [x] Push `main` to `origin/main`.
