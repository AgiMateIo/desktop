"""Configuration manager for the application."""

import json
from pathlib import Path
from typing import Any

from core.constants import (
    DEFAULT_SERVER_URL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_AUTO_CONNECT,
    DEFAULT_RECONNECT_INTERVAL_MS,
)


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._config: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {
            "server_url": DEFAULT_SERVER_URL,
            "api_key": "",
            "device_id": None,
            "auto_connect": DEFAULT_AUTO_CONNECT,
            "reconnect_interval": DEFAULT_RECONNECT_INTERVAL_MS,
            "log_level": DEFAULT_LOG_LEVEL,
        }

    def load(self) -> dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = self._defaults.copy()
            self.save()
        return self._config

    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if default is None:
            default = self._defaults.get(key)
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value

    def update(self, data: dict[str, Any]) -> None:
        """Update multiple configuration values."""
        self._config.update(data)

    @property
    def server_url(self) -> str:
        """Get server URL."""
        return self.get("server_url", "")

    @property
    def api_key(self) -> str:
        """Get API key."""
        return self.get("api_key", "")

    @property
    def device_id(self) -> str | None:
        """Get device ID."""
        return self.get("device_id")

    @device_id.setter
    def device_id(self, value: str) -> None:
        """Set device ID."""
        self.set("device_id", value)
