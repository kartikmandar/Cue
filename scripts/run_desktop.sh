#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${CUE_API_HOST:-127.0.0.1}"
PORT="${CUE_API_PORT:-8765}"
HEALTH_URL="http://${HOST}:${PORT}/health"
APP_PATH="${CUE_APP_PATH:-$ROOT_DIR/build/mac/Build/Products/Release/CueApp.app}"
BACKEND_PID=""

health_ok() {
  python - "$HEALTH_URL" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=0.5) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)

if response.status != 200 or payload.get("status") != "ok" or payload.get("app") != "cue":
    raise SystemExit(1)
PY
}

cleanup() {
  local status=$?
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    printf 'Stopping Cue backend...\n'
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  exit "$status"
}

wait_for_backend() {
  local attempts="${CUE_BACKEND_HEALTH_ATTEMPTS:-80}"
  local delay="${CUE_BACKEND_HEALTH_DELAY:-0.25}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if health_ok; then
      return 0
    fi
    if [[ -n "$BACKEND_PID" ]] && ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      return 1
    fi
    sleep "$delay"
  done
  return 1
}

cd "$ROOT_DIR"

if health_ok; then
  printf 'Cue backend is already healthy at %s\n' "$HEALTH_URL"
else
  printf 'Starting Cue backend at %s\n' "$HEALTH_URL"
  "$ROOT_DIR/scripts/run_backend.sh" &
  BACKEND_PID=$!
  trap cleanup EXIT INT TERM
  if ! wait_for_backend; then
    printf 'Cue backend did not become healthy at %s\n' "$HEALTH_URL" >&2
    exit 1
  fi
fi

if [[ ! -d "$APP_PATH" ]]; then
  printf 'Cue app was not found at %s\n' "$APP_PATH" >&2
  printf 'Build the Release app first with: pixi run package\n' >&2
  exit 1
fi

printf 'Opening Cue app: %s\n' "$APP_PATH"
open "$APP_PATH"

if [[ -n "$BACKEND_PID" ]]; then
  printf 'Cue backend is running. Press Ctrl-C to stop it.\n'
  wait "$BACKEND_PID"
fi
