"""Base classes for the plugin system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import logging

from core.models import ToolResult

logger = logging.getLogger(__name__)


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
    def description(self) -> str:
        """Human-readable plugin description. Override in subclasses."""
        return ""

    @property
    def config_path(self) -> Path:
        """Path to the plugin's config file."""
        return self.plugin_dir / "config.json"

    def validate_config(self) -> tuple[bool, str]:
        """
        Validate plugin configuration values.

        Override in subclasses to add custom validation.

        Returns:
            (is_valid, error_message) tuple
        """
        return True, ""

    def load_config(self) -> dict[str, Any]:
        """
        Load plugin configuration from JSON file with error handling.

        If config file is invalid or missing, plugin is disabled by default.
        """
        if not self.config_path.exists():
            # No config file - use defaults
            self._config = {"enabled": True}
            return self._config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)

            # Validate config values
            valid, error = self.validate_config()
            if not valid:
                logger.error(
                    f"Invalid config values in {self.config_path}: {error}. "
                    f"Plugin '{self.name}' will be disabled."
                )
                self._config = {"enabled": False}

        except json.JSONDecodeError as e:
            logger.error(
                f"Invalid JSON in config file {self.config_path}: {e}. "
                f"Plugin '{self.name}' will be disabled."
            )
            # Disable plugin on invalid config
            self._config = {"enabled": False}
        except Exception as e:
            logger.error(
                f"Failed to load config from {self.config_path}: {e}. "
                f"Plugin '{self.name}' will be disabled."
            )
            # Disable plugin on error
            self._config = {"enabled": False}

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

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return trigger capabilities: {trigger_name: {"params": [...], "description": "..."}}.

        Override in subclasses to declare supported triggers and their parameters.
        """
        return {}


class ToolPlugin(PluginBase):
    """Base class for tool plugins that execute tools."""

    @abstractmethod
    def get_supported_tools(self) -> list[str]:
        """Return list of tool types this plugin can handle."""
        pass

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return tool capabilities: {tool_type: {"params": [...], "description": "..."}}.

        Override in subclasses to declare supported parameters and descriptions.
        Default implementation returns tool types with empty param lists.
        """
        return {tool: {"params": [], "description": ""} for tool in self.get_supported_tools()}

    @abstractmethod
    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        """
        Execute a tool.

        Args:
            tool_type: The type of tool to execute.
            parameters: Parameters for the tool.

        Returns:
            ToolResult with success status and optional data/error.
        """
        pass
