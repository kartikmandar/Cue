# Manual Cua Smoke Test

Task 15 verifies that the real Cua Driver can observe the desktop and perform one
approval-gated safe action before Cue relies on the native app.

Run these steps from `Cue/`. Do not run Task 16 end-to-end validation from this
checklist.

## Boundaries

- Use Pixi as the command surface for project checks.
- Do not run live Cerebras or model calls.
- Do not print, copy, or inspect values from `.env`.
- Do not execute arbitrary terminal commands through Cue.
- Do not store screenshots, logs, or transcripts containing private content.
- Stop after the Cua diagnostics and the optional TextEdit action smoke test.

## Observation Diagnostics

Run the commands below and record whether each returns JSON or clear driver
diagnostics. Permission errors are useful diagnostics when Accessibility or
Screen Recording has not been granted yet.

```bash
cua-driver doctor
cua-driver call list_apps '{}'
cua-driver call list_windows '{}'
cua-driver call get_window_state '{}'
cua-driver call get_screen_size '{}'
cua-driver call get_focused_element '{}'
cua-driver call get_cursor_position '{}'
```

`get_focused_element` and `get_cursor_position` are optional when supported by
the installed Cua Driver version. If either tool is unsupported, record the
driver's diagnostic output and continue.

## Pixi Doctor

Run the project doctor wrapper:

```bash
pixi run doctor
```

Expected result: required diagnostics return JSON or clear driver diagnostics.
Optional diagnostics may report that they are unavailable when supported calls
are not present in the installed driver.

## Safe Action Smoke Test

Only perform this section after the observation diagnostics are understood.

1. Open TextEdit manually, or open it through Cua:

   ```bash
   cua-driver call open_app '{"app_name":"TextEdit"}'
   ```

2. Confirm focus before typing:

   ```bash
   cua-driver call get_window_state '{}'
   cua-driver call get_focused_element '{}'
   ```

   Continue only if the active app/window is TextEdit and the focused element is
   a new, safe text area. If focus is unknown, on a different app, or on existing
   private content, stop without typing.

3. Ask for explicit approval to type one harmless word into TextEdit.

4. After approval, type only the harmless word `Cue`:

   ```bash
   cua-driver call type_text '{"text":"Cue"}'
   ```

5. Re-run observation to verify the active app remains TextEdit:

   ```bash
   cua-driver call get_window_state '{}'
   cua-driver call get_focused_element '{}'
   ```

6. Close the TextEdit document without saving unless the demo operator chooses
   to keep it.

## Result Log Template

```text
Date:
Cua Driver path:
cua-driver doctor:
list_apps:
list_windows:
get_window_state:
get_screen_size:
get_focused_element:
get_cursor_position:
pixi run doctor:
TextEdit action approved by:
Typed word:
Post-action verification:
Notes:
```
