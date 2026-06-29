#!/usr/bin/env bash
set -uo pipefail

status=0

section() {
  printf '\n== %s ==\n' "$*"
}

run_required() {
  local label="$1"
  shift
  section "$label"
  "$@"
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    printf 'Required diagnostic failed with exit code %s: %s\n' "$rc" "$label"
    status="$rc"
  fi
}

run_optional() {
  local label="$1"
  shift
  section "$label"
  "$@"
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    printf 'Optional diagnostic unavailable with exit code %s: %s\n' "$rc" "$label"
  fi
}

call_tool() {
  local tool="$1"
  local payload="${2-}"
  if [[ -z "$payload" ]]; then
    payload="{}"
  fi
  cua-driver call "$tool" "$payload"
}

frontmost_window_payload() {
  call_tool list_windows '{"on_screen_only":true}' | python -c '
import json
import sys

data = json.load(sys.stdin)
windows = [
    window for window in data.get("windows", [])
    if window.get("pid") and window.get("window_id")
]
if not windows:
    raise SystemExit("no on-screen windows with pid/window_id")

window = max(windows, key=lambda item: item.get("z_index", 0))
print(json.dumps({
    "pid": int(window["pid"]),
    "window_id": int(window["window_id"]),
    "capture_mode": "ax",
    "max_elements": 100,
    "max_depth": 10,
}))
'
}

run_window_state() {
  section "get_window_state"
  local payload
  if ! payload="$(frontmost_window_payload)"; then
    printf 'Optional diagnostic unavailable: could not select an on-screen window for get_window_state.\n'
    return
  fi

  call_tool get_window_state "$payload"
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    printf 'Optional diagnostic unavailable with exit code %s: get_window_state\n' "$rc"
  fi
}

if ! command -v cua-driver >/dev/null 2>&1; then
  printf 'cua-driver was not found on PATH.\n'
  printf 'Install or start it with: pixi run install-cua\n'
  exit 127
fi

printf 'cua-driver: %s\n' "$(command -v cua-driver)"

run_required "cua-driver doctor" cua-driver doctor
run_required "list_apps" call_tool list_apps "{}"
run_required "list_windows" call_tool list_windows "{}"
run_optional "check_permissions" call_tool check_permissions '{"prompt":false}'
run_required "get_accessibility_tree" call_tool get_accessibility_tree "{}"
run_window_state
run_required "get_screen_size" call_tool get_screen_size "{}"
run_optional "get_cursor_position" call_tool get_cursor_position "{}"

exit "$status"
