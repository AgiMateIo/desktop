"""
API endpoint and HTTP header constants.

Centralizes server API endpoints and HTTP headers used for communication.
"""

# API Endpoints
ENDPOINT_DEVICE_LINK = "/device/app/registration/link"
ENDPOINT_DEVICE_TRIGGER = "/device/app/trigger/new"
ENDPOINT_CENTRIFUGO_TOKEN = "/device/app/centrifugo/token"
ENDPOINT_TOOL_RESULT = "/device/app/tools/result"
ENDPOINT_WEBSOCKET = "/connection/websocket"

# HTTP Headers
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_DEVICE_AUTH = "X-App-Auth-Key"
CONTENT_TYPE_JSON = "application/json"
