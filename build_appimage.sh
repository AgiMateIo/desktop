#!/bin/bash
# Build Linux AppImage using python-appimage in Docker
# Provides isolation and reproducibility on any system
#
# Usage:
#   ./build_appimage.sh                  # Build for current architecture
#   ./build_appimage.sh --arch arm64     # Build for ARM64 (requires QEMU on x86)
#   ./build_appimage.sh --arch amd64     # Build for x86_64
#   ./build_appimage.sh --native         # Build without Docker (Linux only)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_VERSION="3.11"
APP_NAME="SystemAgent"
USE_DOCKER=true
PLATFORM=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --native)
            USE_DOCKER=false
            if [[ "$(uname)" != "Linux" ]]; then
                echo "Error: --native only works on Linux"
                exit 1
            fi
            shift
            ;;
        --arch)
            PLATFORM="linux/$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=== Building ${APP_NAME} AppImage ==="

if [[ "$USE_DOCKER" == true ]]; then
    PLATFORM_FLAG=""
    if [[ -n "$PLATFORM" ]]; then
        PLATFORM_FLAG="--platform ${PLATFORM}"
        echo "Building in Docker container for ${PLATFORM}..."
    else
        echo "Building in Docker container..."
    fi

    docker run --rm ${PLATFORM_FLAG} \
        -v "${SCRIPT_DIR}:/app" \
        -w /app \
        python:${PYTHON_VERSION}-slim-bookworm \
        bash -c "
            apt-get update && apt-get install -y --no-install-recommends file > /dev/null 2>&1 &&
            pip install --quiet python-appimage &&
            python -m python_appimage build app \
                --python-version ${PYTHON_VERSION} \
                --name ${APP_NAME} \
                --entrypoint /app/entrypoint \
                /app
        "
else
    echo "Building natively..."

    if ! python3 -m pip show python-appimage > /dev/null 2>&1; then
        echo "Installing python-appimage..."
        python3 -m pip install python-appimage
    fi

    python3 -m python_appimage build app \
        --python-version "${PYTHON_VERSION}" \
        --name "${APP_NAME}" \
        --entrypoint "${SCRIPT_DIR}/entrypoint" \
        "${SCRIPT_DIR}"
fi

# Move result to dist
mkdir -p "${SCRIPT_DIR}/dist"
mv -f "${SCRIPT_DIR}"/${APP_NAME}-*.AppImage "${SCRIPT_DIR}/dist/" 2>/dev/null || true

echo ""
echo "=== Done! ==="
ls -la "${SCRIPT_DIR}/dist/"*.AppImage 2>/dev/null || echo "AppImage created in current directory"
