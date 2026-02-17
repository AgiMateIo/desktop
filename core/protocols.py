"""Protocol definitions for dependency injection.

Defines interfaces for core components to enable loose coupling and testability.
"""

from pathlib import Path
from typing import Protocol, Any, Callable, runtime_checkable, TYPE_CHECKING

from .models import TriggerPayload, ToolTask, ToolResult
from .plugin_base import PluginEvent, TrayMenuItem, TriggerPlugin, ToolPlugin

if TYPE_CHECKING:
    from ui.tray import ConnectionStatus


@runtime_checkable
class IConfigManager(Protocol):
    """Interface for configuration management."""

    @property
    def server_url(self) -> str:
        """Get server URL."""
        ...

    @property
    def device_key(self) -> str:
        """Get device key."""
        ...

    @property
    def device_id(self) -> str | None:
        """Get device ID."""
        ...

    @device_id.setter
    def device_id(self, value: str) -> None:
        """Set device ID."""
        ...

    def load(self) -> dict[str, Any]:
        """Load configuration from file."""
        ...

    def save(self) -> None:
        """Save configuration to file."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        ...

    def update(self, data: dict[str, Any]) -> None:
        """Update multiple configuration values."""
        ...


@runtime_checkable
class IDeviceInfo(Protocol):
    """Interface for device information."""

    @property
    def device_id(self) -> str:
        """Get unique device ID."""
        ...

    def get_platform(self) -> str:
        """Get platform name (e.g., 'macos', 'windows', 'linux')."""
        ...

    def get_hostname(self) -> str:
        """Get device hostname."""
        ...

    def get_system_info(self) -> dict[str, str]:
        """Get system information."""
        ...


@runtime_checkable
class IPluginManager(Protocol):
    """Interface for plugin management."""

    @property
    def triggers(self) -> dict[str, TriggerPlugin]:
        """Get all trigger plugins."""
        ...

    @property
    def tools(self) -> dict[str, ToolPlugin]:
        """Get all tool plugins."""
        ...

    def on_event(self, handler: Callable[[PluginEvent], None]) -> None:
        """Register a global event handler for all plugin events."""
        ...

    def discover_plugins(self) -> None:
        """Discover all available plugins in the plugins directory."""
        ...

    async def initialize_all(self) -> None:
        """Initialize all loaded plugins."""
        ...

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        ...

    async def start_triggers(self) -> None:
        """Start all enabled trigger plugins."""
        ...

    async def stop_triggers(self) -> None:
        """Stop all running trigger plugins."""
        ...

    async def execute_tool(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        """Execute a tool by type."""
        ...

    def get_all_tray_items(
        self,
        on_plugin_click: Callable[[str], None] | None = None
    ) -> list[TrayMenuItem]:
        """Get tray menu items from all plugins."""
        ...

    def get_supported_tool_types(self) -> list[str]:
        """Get all supported tool types across all plugins."""
        ...

    def get_capabilities(self) -> dict:
        """Get aggregated capabilities from all enabled plugins."""
        ...

    def get_failed_plugins(self) -> dict[str, Any]:
        """Get plugins that failed to load."""
        ...


@runtime_checkable
class IServerClient(Protocol):
    """Interface for server communication."""

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        ...

    @property
    def server_url(self) -> str:
        """Get the server URL."""
        ...

    def on_tool_call(self, handler: Callable[[ToolTask], None]) -> None:
        """Register a handler for incoming tool calls."""
        ...

    async def send_trigger(self, payload: TriggerPayload) -> bool:
        """Send a trigger event to the server."""
        ...

    async def link_device(self, device_os: str, device_name: str, capabilities: dict | None = None) -> bool:
        """Link device with the server."""
        ...

    async def connect(self) -> bool:
        """Connect to the WebSocket server."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        ...

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        ...


@runtime_checkable
class ITrayManager(Protocol):
    """Interface for system tray management."""

    def show(self) -> None:
        """Show the tray icon."""
        ...

    def hide(self) -> None:
        """Hide the tray icon."""
        ...

    def set_connection_status(self, status: "ConnectionStatus") -> None:
        """Set the connection status (updates icon, tooltip, menu)."""
        ...

    def show_message(
        self,
        title: str,
        message: str,
        icon: Any = None,
        duration: int = 5000,
        notification_type: Any = None
    ) -> bool | None:
        """Show a notification message."""
        ...

    def set_plugin_items(self, items: list[TrayMenuItem]) -> None:
        """Set plugin menu items."""
        ...

    def on_settings_requested(self, callback: Callable[[], None]) -> None:
        """Register callback for settings menu item."""
        ...

    def on_quit_requested(self, callback: Callable[[], None]) -> None:
        """Register callback for quit menu item."""
        ...
