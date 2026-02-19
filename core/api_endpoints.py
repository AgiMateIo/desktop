"""
API endpoint and HTTP header constants.

Centralizes server API endpoints and HTTP headers used for communication.
"""

# API Endpoints
ENDPOINT_DEVICE_LINK = "/device/registration/link"
ENDPOINT_DEVICE_TRIGGER = "/app/trigger/new"
ENDPOINT_CENTRIFUGO_TOKEN = "/app/centrifugo/token"
ENDPOINT_WEBSOCKET = "/connection/websocket"

# HTTP Headers
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_DEVICE_AUTH = "X-App-Auth-Key"
CONTENT_TYPE_JSON = "application/json"
