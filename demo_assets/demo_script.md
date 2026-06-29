# Cue Demo Runbook

This is the Task 16 recording runbook for the exact hackathon video story. It
reflects the latest validation pass and keeps Cua-dependent actions separated
from safe read-only staging.

## Before Recording

1. Close personal apps, private browser tabs, email, chat, password managers,
   and unrelated terminals.
2. Disable notifications and Focus interruptions.
3. Keep the desktop on the local `Cue/` project only.
4. Do not show or print `Cue/.env`; confirm the app only reports whether the
   Cerebras key is configured.
5. Use synthetic assets from `Cue/demo_assets/` only.
6. Do not approve typing into TextEdit or pasting into Terminal until the
   recording owner is ready.
7. Run live Cerebras/model calls only when the recording owner approves it and
   the key is configured off-screen.

## Validation Snapshot

Latest non-interactive validation from June 29, 2026:

| Item | Status | Evidence |
|---|---|---|
| Python suite | Passed | `pixi run test` collected 138 tests and all passed. |
| Swift suite | Passed | `pixi run test-mac` executed 6 tests and `TEST SUCCEEDED`. |
| Cua doctor | Passed | `pixi run doctor` found Cua Driver 0.6.8 with Accessibility and Screen Recording granted. |
| Backend health | Passed | `GET /health` returned `{"status":"ok","app":"cue"}`. |
| Release package | Passed | `pixi run package` created `dist/CueApp.zip`. |
| Native app launch | Passed | `pixi run app` started Release `CueApp.app`; Cua AX inspection found Cue onboarding/privacy/policy/permissions state without screenshots. |
| Cerebras smoke | Passed | A live `gemma-4-31b` smoke call returned the expected response in 351 ms without printing `.env`. |
| Demo dry run | Passed | `pixi run demo --dry-run` listed local PDF, dashboard, form, TextEdit, and Terminal targets without opening apps. |

Read-only CLI/backend previews also showed:

- Focus summary returns explicit unknown app/window/focus/cursor fields when
  Cua cannot observe a field.
- `Type the password from this page.` is blocked with no workflow action.
- Terminal/Claude Code handoff previews require approval and do not run a
  command by default.
- TextEdit previews `open TextEdit -> verify -> type title and move below ->
  verify`, then waits for approval before any typing.

## Start The Demo Surface

1. Run `pixi run doctor`.
   - If it says `cua-driver was not found on PATH`, run `pixi run install-cua`,
     grant macOS permissions, then run `pixi run doctor` again.
   - Continue only when Cua can observe apps/windows or when the Cua diagnostic
     itself is the intended blocker being shown.
2. Run `pixi run test`.
3. Run `pixi run test-mac`.
4. Run `pixi run package`.
5. Run `pixi run desktop` to start the backend and launch the packaged native
   Cue app. For manual two-terminal staging, run `pixi run backend` first and
   then `pixi run app`.
7. Confirm health from another terminal:

```bash
curl -sS http://127.0.0.1:8765/health
```

Expected:

```json
{"status":"ok","app":"cue"}
```

8. Optional staging check: run `pixi run demo --dry-run`.
9. To open deterministic local materials, run `pixi run demo`.

## 60-Second Flow

1. Desktop/title, 0-6 seconds:
   - Say: "Blind and low-vision workers do real desk jobs across PDFs, browsers,
     documents, terminals, dashboards, and code tools. Cue turns the Mac desktop
     into an approved work operator."
2. Cue palette, 6-16 seconds:
   - Ask: `What app am I in, what window is active, and where is my focus?`
   - Show active app/window/focus/cursor, or explicit unknown fields if Cua
     cannot observe a field. No action should execute.
3. Local PDF/dashboard, 16-30 seconds:
   - Open the local dashboard or hackathon PDF.
   - Ask: `Summarize the current PDF or dashboard and tell me what I should do next.`
   - Show a read-only explanation and safe next-step proposal. Do not approve a
     state-changing action unless it is the local demo form and the preview is
     visible.
4. TextEdit workflow, 30-42 seconds:
   - Ask: `Open TextEdit and type the project name Cue as a title, then put the cursor below it.`
   - Show workflow preview and approval gate.
   - Approve only after the preview clearly targets TextEdit and the recording
     owner is ready for harmless typing.
   - Show verification/narration after the step.
5. Terminal/Claude Code handoff, 42-50 seconds:
   - Ask: `Open Terminal for this project and prepare a Claude Code prompt that asks it to inspect the repo.`
   - Show Terminal launch/focus or a prepared prompt only after approval.
   - Do not let Cue run arbitrary commands by default.
6. Product trust panel, 50-57 seconds:
   - Show policy tier, confirmation state, verification state, redacted audit,
     strict privacy mode, and timing.
   - If live model calls remain disabled, say "backend timing is visible; real
     Cerebras latency is disabled for this validation run."
7. Closing, 57-60 seconds:
   - Say: "Cua powers Cue. Cue plans, asks, acts, verifies, and narrates."

## Safety Checks To Rehearse

1. Sensitive blocker:
   - Open `demo_assets/inaccessible_form.html` or another safe local page with
     the word `password`.
   - Ask: `Type the password from this page.`
   - Expected: blocked sensitive-workflow state; no typing occurs.
2. Focus drift guard:
   - Preview a TextEdit action.
   - Switch to another app before confirming.
   - Confirm.
   - Expected: Cue refuses execution, re-observes, and asks for renewed
     confirmation.
3. Terminal guard:
   - Ask for a Claude Code prompt.
   - Confirm that Cue prepares or pastes only after approval and does not run a
     command by default.

## What To Say

"Cue is a blind-first Mac work operator. Cua powers desktop observation and
actions. Cerebras Gemma 4 powers fast planning, explanation, verification, and
narration. Cue plans, asks, acts, verifies, and narrates without storing raw
screenshots by default."

## Safety Notes

- Do not use personal documents or real workplace data.
- Do not run unsafe Cua action smoke tests here; use only the approved local
  recording prompts.
- Do not run live model calls from the demo helper itself.
- Do not execute arbitrary Terminal commands; Terminal is opened only for safe
  handoff preparation.
- Do not claim real Cerebras latency in a recording unless live model calls were
  explicitly enabled and observed for that recording take.
