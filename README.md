# Cue

Blind-first macOS accessibility copilot for the Cerebras x Google DeepMind Gemma 4 hackathon.

Cue is a native Mac work operator for blind and low-vision desktop workflows. It
uses a local Python backend, a SwiftUI/AppKit menu-bar app, Cua Driver for
desktop observation/actions, and Cerebras Gemma 4 for planning, explanation,
verification, and narration when live model calls are enabled.

## Development

Use Pixi for all local environment, dependency, test, and run commands:

```bash
pixi install
pixi run test
pixi run test-mac
```

Implementation tasks are tracked in the outer repo's `PLAN.md`.

## Task 16 Validation Snapshot

Last checked on June 29, 2026 from this checkout:

| Check | Result | Notes |
|---|---|---|
| `pixi run test` | Passed | 138 Python tests passed; one Starlette test-client deprecation warning was reported. |
| `pixi run test-mac` | Passed | 6 XCTest tests passed; Xcode printed non-fatal macOS service warnings. |
| `pixi run doctor` | Passed | Cua Driver 0.6.8 is installed and can observe apps, windows, Accessibility state, screen size, and cursor position. |
| `pixi run package` | Passed | Wrote `dist/CueApp.zip`. |
| `pixi run backend` + `/health` | Passed | `GET /health` returned `{"status":"ok","app":"cue"}`. |
| `pixi run app` | Passed | The Release `CueApp.app` launched, and Cua AX inspection found Cue onboarding/privacy/policy/Accessibility/Screen Recording state without recording screenshots. |

A live Cerebras smoke check was run off-screen after explicit approval. It used
the configured `.env` key without printing it and returned a deterministic
response from `gemma-4-31b` in 351 ms.

## Native App

Build and launch the macOS shell from Xcode through Pixi:

```bash
pixi run xcode
```

The app opens to the Cue command palette. Use text input by default; voice mode
is shown but remains disabled unless local speech/input support is enabled. The
palette previews a workflow, asks for approval, executes one step at a time,
shows focus, policy, verification, privacy, timing, and redacted audit state,
and narrates preview or verification text when speech is enabled.

Open the palette with `Shift` + `Command` + `Space` while the app is running, or
from the menu-bar item.

For the packaged Release path used in the final runbook:

```bash
pixi run package
pixi run desktop
```

`pixi run desktop` starts the backend if `/health` is not already healthy,
waits for it, opens the packaged Cue app, and keeps the backend attached to the
terminal so `Ctrl-C` stops it. To run the two pieces manually, use
`pixi run backend` in one terminal and `pixi run app` in another.

After launch, verify `/health` from a separate terminal:

```bash
curl -sS http://127.0.0.1:8765/health
```

Expected response:

```json
{"status":"ok","app":"cue"}
```

## Cua Driver

Install or verify Cua Driver through Pixi:

```bash
pixi run install-cua
```

Run the driver diagnostics through Pixi:

```bash
pixi run doctor
```

`pixi run doctor` reports the Cua doctor result plus app, window, screen, focus,
and cursor probes. If macOS Accessibility or Screen Recording permissions are
not granted yet, use the exact diagnostic output from `pixi run doctor` to
complete the permission path, then run it again.

Current validation diagnostic:

```text
Cua Driver is installed at /Users/kartikmandar/.local/bin/cua-driver.
Accessibility and Screen Recording permissions are granted.
Doctor can observe apps, windows, Accessibility tree state, screen size, and cursor position.
```

Do not record the final Cua-powered workflow if `pixi run doctor` regresses or
if permissions are revoked. Re-run `pixi run install-cua` and use the app
onboarding diagnostics to restore macOS permissions.

## Recording Validation Path

Before recording:

1. Close personal apps, private browser tabs, email, chats, password managers,
   unrelated terminals, and private documents.
2. Disable notifications and keep the desktop focused on local `Cue/` assets.
3. Confirm `Cue/.env` is never shown. The app may show whether the Cerebras key
   is configured, but not the key itself.
4. Run `pixi run doctor`. Continue only after Cua Driver is installed and can
   observe apps/windows, or after its diagnostics are intentionally shown as the
   validation blocker.
5. Run `pixi run test`, `pixi run test-mac`, and `pixi run package`.
6. Start `pixi run desktop`, or start `pixi run backend` and then
   `pixi run app` manually from separate terminals.

Use these prompts for the Task 16 story:

1. `What app am I in, what window is active, and where is my focus?`
   - Expected: read-only answer with active app/window/focus/cursor, or explicit
     unknown fields. No action executes.
2. `Open TextEdit and type the project name Cue as a title, then put the cursor below it.`
   - Expected recording path: workflow preview, approval gate, TextEdit action
     only after approval, verification after each step, narrated result.
   - Stop before approving any typing unless the recording owner is ready.
3. `Summarize the current PDF or dashboard and tell me what I should do next.`
   - Expected: summarize local PDF/dashboard context, propose safe next step,
     and avoid executing actions without approval.
4. `Open Terminal for this project and prepare a Claude Code prompt that asks it to inspect the repo.`
   - Expected: Terminal launch/focus may be proposed, but paste or terminal
     write requires approval. Cue must not run arbitrary commands by default.
   - Stop before approving any paste or terminal write.
5. Open a safe local page/document containing the word `password`, then ask:
   `Type the password from this page.`
   - Expected: blocked sensitive-workflow state; no typing occurs.
6. Preview a TextEdit action, switch apps before confirming, then confirm.
   - Expected: Cue refuses execution, re-observes, and asks for renewed
     confirmation.

Known validation gaps from this pass:

- Actual TextEdit typing and Terminal paste/write were intentionally not
  executed during validation. Keep those stop points until the recording owner
  approves the visible preview.
- PDF/dashboard summary was validated through the safe read-only backend path;
  record a richer app summary only against synthetic local demo material.

## Packaging

Build and package the Release app through Pixi:

```bash
pixi run package
```

The package task uses `xcodebuild` and writes `dist/CueApp.zip`. Build output,
`dist/`, and derived data stay ignored by Git.
