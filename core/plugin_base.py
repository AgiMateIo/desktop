"""Base classes for the plugin system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json


@dataclass
class TrayMenuItem:
    """Represents a menu item for the system tray."""

    id: str
    label: str
    callback: Callable[[], None] | None = None
    icon: str | None = None
    children: list["TrayMenuItem"] = field(default_factory=list)
    separator_after: bool = False


@dataclass
class PluginEvent:
    """Event emitted by a plugin."""

    plugin_id: str
    event_name: str
    data: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """Abstract base class for all plugins."""

    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.plugin_id = plugin_dir.name
        self._config: dict[str, Any] = {}
        self._event_handlers: list[Callable[[PluginEvent], None]] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        pass

    @property
    def config_path(self) -> Path:
        """Path to the plugin's config file."""
        return self.plugin_dir / "config.json"

    def load_config(self) -> dict[str, Any]:
        """Load plugin configuration from JSON file."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        return self._config

    def save_config(self) -> None:
        """Save plugin configuration to JSON file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value

    @property
    def enabled(self) -> bool:
        """Check if the plugin is enabled."""
        return self._config.get("enabled", True)

    def on_event(self, handler: Callable[[PluginEvent], None]) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)

    def emit_event(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to all registered handlers."""
        event = PluginEvent(
            plugin_id=self.plugin_id,
            event_name=event_name,
            data=data or {}
        )
        for handler in self._event_handlers:
            handler(event)

    def get_tray_menu_items(self) -> list[TrayMenuItem]:
        """Return menu items for the system tray. Override in subclasses."""
        return []

    def has_window(self) -> bool:
        """Return True if plugin has a UI window. Override in subclasses."""
        return False

    def create_window(self, parent=None):
        """Create and return the plugin's UI window. Override in subclasses."""
        return None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin. Called once at startup."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the plugin. Called once at exit."""
        pass


class TriggerPlugin(PluginBase):
    """Base class for trigger plugins that monitor events and emit triggers."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._running = False

    @property
    def running(self) -> bool:
        """Check if the trigger is currently running."""
        return self._running

    @abstractmethod
    async def start(self) -> None:
        """Start monitoring for triggers."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop monitoring for triggers."""
        pass


class ActionPlugin(PluginBase):
    """Base class for action plugins that execute actions."""

    @abstractmethod
    def get_supported_actions(self) -> list[str]:
        """Return list of action types this plugin can handle."""
        pass

    @abstractmethod
    async def execute(self, action_type: str, parameters: dict[str, Any]) -> bool:
        """
        Execute an action.

        Args:
            action_type: The type of action to execute.
            parameters: Parameters for the action.

        Returns:
            True if the action was executed successfully, False otherwise.
        """
        pass
