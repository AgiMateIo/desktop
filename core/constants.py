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

# Application Identifiers
APP_NAME = "Agimate Desktop"
APP_SOURCE_ID = "desktop-agent"

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
