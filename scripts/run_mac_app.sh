#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

project="apps/mac/CueApp/CueApp.xcodeproj"
scheme="CueApp"
derived_data_path="build/mac"
app_path="$derived_data_path/Build/Products/Debug/CueApp.app"

if [[ "${CUE_OPEN_XCODE:-0}" == "1" ]]; then
  open "$project"
  exit 0
fi

xcodebuild \
  -project "$project" \
  -scheme "$scheme" \
  -configuration Debug \
  -derivedDataPath "$derived_data_path" \
  build

open "$app_path"
