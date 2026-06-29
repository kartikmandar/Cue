#!/usr/bin/env bash
set -euo pipefail

INSTALL_URL="https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.sh"

log() {
  printf '%s\n' "$*"
}

has_cua_driver() {
  command -v cua-driver >/dev/null 2>&1
}

open_cua_app_if_present() {
  local app_path
  for app_path in \
    "/Applications/Cua.app" \
    "/Applications/CuaDriver.app" \
    "/Applications/Cua Driver.app" \
    "$HOME/Applications/Cua.app" \
    "$HOME/Applications/CuaDriver.app" \
    "$HOME/Applications/Cua Driver.app"; do
    if [[ -d "$app_path" ]]; then
      log "Opening Cua app: $app_path"
      open "$app_path"
      return 0
    fi
  done

  log "Cua app bundle was not found in /Applications or ~/Applications."
  return 1
}

if has_cua_driver; then
  log "cua-driver is already installed at: $(command -v cua-driver)"
  open_cua_app_if_present || true
else
  if ! command -v curl >/dev/null 2>&1; then
    log "curl is required to install Cua Driver, but it was not found."
    exit 127
  fi

  installer="$(mktemp -t cue-cua-driver-install.XXXXXX.sh)"
  trap 'rm -f "$installer"' EXIT

  log "Downloading official Cua Driver installer:"
  log "$INSTALL_URL"
  curl -fsSL "$INSTALL_URL" -o "$installer"
  chmod +x "$installer"
  bash "$installer"

  if ! has_cua_driver; then
    log "Cua Driver installer finished, but cua-driver is still not on PATH."
    log "Open the Cua app, complete setup, then re-run: pixi run doctor"
    open_cua_app_if_present || true
    exit 1
  fi

  log "cua-driver installed at: $(command -v cua-driver)"
  open_cua_app_if_present || true
fi

log "Running Cua Driver doctor. Permission warnings here are expected until macOS Accessibility and Screen Recording are granted."
if cua-driver doctor; then
  log "Cua Driver install/verification completed."
else
  status=$?
  log "cua-driver doctor reported a problem. Open Cua and grant requested permissions, then run: pixi run doctor"
  exit "$status"
fi
