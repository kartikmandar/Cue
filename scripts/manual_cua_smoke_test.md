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
cua-driver call check_permissions '{"prompt":false}'
cua-driver call list_apps '{}'
cua-driver call list_windows '{}'
cua-driver call list_windows '{"on_screen_only":true}'
cua-driver call get_accessibility_tree '{}'
cua-driver call get_window_state '{"pid":123,"window_id":456,"capture_mode":"ax","max_elements":100,"max_depth":10}'
cua-driver call get_screen_size '{}'
cua-driver call get_cursor_position '{}'
```

Replace the sample `pid` and `window_id` in `get_window_state` with values from
the on-screen `list_windows` result. `get_window_state` is AX-only here so the
smoke test does not capture a screenshot. `get_cursor_position` is optional when
supported by the installed Cua Driver version. If a tool is unsupported, record
the driver's diagnostic output and continue.

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
   cua-driver call launch_app '{"bundle_id":"com.apple.TextEdit"}'
   ```

2. Confirm focus before typing:

   ```bash
   cua-driver call list_windows '{"on_screen_only":true}'
   cua-driver call get_window_state '{"pid":123,"window_id":456,"capture_mode":"ax","max_elements":100,"max_depth":10}'
   ```

   Replace the sample `pid` and `window_id` with TextEdit's values from
   `list_windows`. Continue only if the active app/window is TextEdit and the AX
   state shows a new, safe text area. If focus is unknown, on a different app, or
   on existing private content, stop without typing.

3. Ask for explicit approval to type one harmless word into TextEdit.

4. After approval, type only the harmless word `Cue`:

   ```bash
   cua-driver call type_text '{"text":"Cue"}'
   ```

5. Re-run observation to verify the active app remains TextEdit:

   ```bash
   cua-driver call list_windows '{"on_screen_only":true}'
   cua-driver call get_window_state '{"pid":123,"window_id":456,"capture_mode":"ax","max_elements":100,"max_depth":10}'
   ```

6. Close the TextEdit document without saving unless the demo operator chooses
   to keep it.

## Result Log Template

```text
Date:
Cua Driver path:
cua-driver doctor:
check_permissions:
list_apps:
list_windows:
get_window_state:
get_screen_size:
get_cursor_position:
pixi run doctor:
TextEdit action approved by:
Typed word:
Post-action verification:
Notes:
```
