"""Data models for server communication."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from core.tool_types import EVENT_TYPE_DEVICE
from core.constants import APP_SOURCE_ID


@dataclass
class TriggerPayload:
    """Payload for sending a trigger event to the server."""

    name: str                          # Event name (e.g., "desktop.trigger.filewatcher.created")
    data: dict[str, Any]               # Additional event data
    device_id: str                     # Unique device ID
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = EVENT_TYPE_DEVICE      # Always "DEVICE_EVENT"
    source: str = APP_SOURCE_ID        # Source identifier
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (camelCase for server)."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "source": self.source,
            "deviceId": self.device_id,
            "occurredAt": self.occurred_at,
            "data": self.data
        }


@dataclass
class ToolTask:
    """Tool task received from the server."""

    id: str                            # Server-issued tool call ID (opaque string, echoed back as-is)
    name: str                          # Tool name (e.g., "desktop.tool.notification.show")
    params: dict[str, Any]             # Tool parameters
    connector_code: str | None = None  # Connector code (informational)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolTask":
        """Create from dictionary.

        Accepts both the bare toolCall payload and the enveloped form
        {"type": "toolCall", "payload": {...}}. Tool parameters arrive
        in "input" (current contract) or "params" (legacy).
        """
        if isinstance(data.get("payload"), dict):
            data = data["payload"]
        params = data.get("input")
        if not isinstance(params, dict):
            params = data.get("params", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            params=params,
            connector_code=data.get("connectorCode"),
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
