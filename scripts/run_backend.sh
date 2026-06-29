#!/usr/bin/env bash
set -euo pipefail

HOST="${CUE_API_HOST:-127.0.0.1}"
PORT="${CUE_API_PORT:-8765}"

exec python -m uvicorn "cue.api:create_app" --factory --host "$HOST" --port "$PORT"
