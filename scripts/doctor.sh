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
  local payload="${2:-{}}"
  cua-driver call "$tool" "$payload"
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
run_required "get_window_state" call_tool get_window_state "{}"
run_required "get_screen_size" call_tool get_screen_size "{}"
run_optional "get_focused_element" call_tool get_focused_element "{}"
run_optional "get_cursor_position" call_tool get_cursor_position "{}"

exit "$status"
