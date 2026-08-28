"""
Core application constants.

Centralizes configuration defaults, timeouts, and application identifiers.
"""

# Duration Constants (milliseconds)
DEFAULT_NOTIFICATION_DURATION_MS = 5000
DEFAULT_RECONNECT_INTERVAL_MS = 5000
MIN_RECONNECT_INTERVAL_MS = 1000
MAX_RECONNECT_INTERVAL_MS = 60000
DEFAULT_HTTP_TIMEOUT_MS = 10000

# Connection Constants
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10

# How many recent tool call IDs to remember for duplicate suppression.
# Centrifugo delivers at-least-once, so the same toolCall can arrive twice
# (e.g. re-delivered on reconnect) and must not be executed twice.
TOOL_CALL_HISTORY_SIZE = 256

# Application Identifiers
APP_NAME = "Agimate Desktop"
APP_SOURCE_ID = "desktop-agent"

# The version the app reports to the backend, and the one the macOS bundle
# carries — agimate_desktop.spec reads it from here so the two cannot drift.
# pyproject.toml keeps its own copy because uv needs a literal; bump both.
APP_VERSION = "0.3.0"

# Default Configuration Values
DEFAULT_SERVER_URL = "https://api.agimate.io"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_AUTO_CONNECT = True

# MCP Server
DEFAULT_MCP_PORT = 9999
DEFAULT_MCP_HOST = "127.0.0.1"

# Platform Identifiers
PLATFORM_MACOS = "Darwin"
PLATFORM_LINUX = "Linux"
PLATFORM_WINDOWS = "Windows"
