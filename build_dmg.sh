#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="AgimateDesktop"
APP_PATH="${SCRIPT_DIR}/dist/${APP_NAME}.app"
DMG_PATH="${SCRIPT_DIR}/dist/${APP_NAME}.dmg"
TEMP_DIR=$(mktemp -d)

# Check .app exists
if [ ! -d "$APP_PATH" ]; then
    echo "Error: ${APP_PATH} not found. Run 'python build.py build' first."
    exit 1
fi

echo "=== Building ${APP_NAME}.dmg ==="

# Prepare DMG contents
cp -R "$APP_PATH" "${TEMP_DIR}/"
ln -s /Applications "${TEMP_DIR}/Applications"

# Remove old DMG if exists
rm -f "$DMG_PATH"

# Create DMG
hdiutil create "$DMG_PATH" \
    -volname "$APP_NAME" \
    -srcfolder "$TEMP_DIR" \
    -ov -format UDZO

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "=== Done! ==="
ls -la "$DMG_PATH"
