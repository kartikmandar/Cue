# Cue Demo Runbook

## Before Recording

1. Close personal apps, private browser tabs, email, chat, password managers,
   and unrelated terminals.
2. Disable notifications and Focus interruptions.
3. Keep the desktop on the local `Cue/` project only.
4. Do not show or print `Cue/.env`; confirm the app only reports whether the
   Cerebras key is configured.
5. Use synthetic assets from `Cue/demo_assets/` only.

## Start The Demo Surface

1. Terminal 1: run `pixi run backend`.
2. Terminal 2: run `pixi run app` to launch the native Cue app.
3. Optional staging check: run `pixi run demo --dry-run`.
4. To open the deterministic local materials, run `pixi run demo`.

## 60-Second Flow

1. Open the Cue palette and ask: "Open the project brief and tell me what I need
   to do."
2. Show Cue opening or focusing the brief, narrating the summary, and requiring
   approval before any change.
3. Open the hackathon PDF or the local dashboard and ask Cue to explain what is
   on the page, where focus is, and what to do next.
4. Use the weakly labeled local form to show that Cue can identify a safe local
   field and ask before filling it.
5. Ask for the TextEdit path: "Open TextEdit, add Cue as a title, and put the
   cursor below it." Approve only after the workflow preview is visible.
6. Ask for the Terminal path: "Open Terminal for this project and prepare a
   read-only Claude Code prompt." Show that Cue prepares or explains the prompt
   without running arbitrary commands.
7. Show the product-trust panel: verification result, policy tier, redacted
   audit event, strict privacy status, and Cerebras latency/timing.

## What To Say

"Cue is a blind-first Mac work operator. Cua powers desktop observation and
actions. Cerebras Gemma 4 powers fast planning, explanation, verification, and
narration. Cue plans, asks, acts, verifies, and narrates without storing raw
screenshots by default."

## Safety Notes

- Do not use personal documents or real workplace data.
- Do not run Cua smoke tests here; Task 15 owns real Cua validation.
- Do not run live model calls from the demo helper itself.
- Do not execute arbitrary Terminal commands; Terminal is opened only for safe
  handoff preparation.
