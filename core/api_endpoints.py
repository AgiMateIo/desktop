"""
API endpoint and HTTP header constants.

Centralizes server API endpoints and HTTP headers used for communication.
"""

# API Endpoints
ENDPOINT_DEVICE_LINK = "/mobile-api/device/registration/link"
ENDPOINT_DEVICE_TRIGGER = "/mobile-api/device/trigger/new"
ENDPOINT_WEBSOCKET = "/connection/websocket"

# HTTP Headers
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_DEVICE_AUTH = "X-Device-Auth-Key"
CONTENT_TYPE_JSON = "application/json"
