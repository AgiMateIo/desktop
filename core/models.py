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
    user_id: str | None = None         # User ID (null for device events)
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (camelCase for server)."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "source": self.source,
            "deviceId": self.device_id,
            "userId": self.user_id,
            "occurredAt": self.occurred_at,
            "data": self.data
        }


@dataclass
class ToolTask:
    """Tool task received from the server."""

    type: str                          # Tool type (e.g., "desktop.tool.notification.show")
    parameters: dict[str, Any]         # Tool parameters

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolTask":
        """Create from dictionary."""
        return cls(
            type=data.get("type", ""),
            parameters=data.get("parameters", {})
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
