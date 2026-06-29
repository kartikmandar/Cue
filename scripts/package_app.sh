#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_PATH="$ROOT_DIR/apps/mac/CueApp/CueApp.xcodeproj"
DERIVED_DATA_PATH="$ROOT_DIR/build/mac"
APP_PATH="$DERIVED_DATA_PATH/Build/Products/Release/CueApp.app"
DIST_DIR="$ROOT_DIR/dist"
ZIP_PATH="$DIST_DIR/CueApp.zip"

# The release artifact for the hackathon handoff is dist/CueApp.zip.
mkdir -p "$DIST_DIR"

xcodebuild \
  -project "$PROJECT_PATH" \
  -scheme CueApp \
  -configuration Release \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  CODE_SIGNING_ALLOWED=NO \
  build

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected Release app not found at $APP_PATH" >&2
  exit 1
fi

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH" || (
  cd "$(dirname "$APP_PATH")"
  zip -qry "$ZIP_PATH" "$(basename "$APP_PATH")"
)

echo "Packaged $ZIP_PATH"
