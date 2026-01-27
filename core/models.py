"""Data models for server communication."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

from core.action_types import EVENT_TYPE_DEVICE
from core.constants import APP_SOURCE_ID


@dataclass
class TriggerPayload:
    """Payload for sending a trigger event to the server."""

    name: str                          # Event name (e.g., "device.file.created")
    data: dict[str, Any]               # Additional event data
    device_id: str                     # Unique device ID
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = EVENT_TYPE_DEVICE      # Always "DEVICE_EVENT"
    source: str = APP_SOURCE_ID        # Source identifier
    user_id: str | None = None         # User ID (null for device events)
    occurred_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

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
class ActionTask:
    """Action task received from the server."""

    type: str                          # Action type (e.g., "NOTIFICATION", "TTS")
    parameters: dict[str, Any]         # Action parameters

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionTask":
        """Create from dictionary."""
        return cls(
            type=data.get("type", ""),
            parameters=data.get("parameters", {})
        )
