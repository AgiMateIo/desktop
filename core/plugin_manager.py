"""Plugin manager for discovering, loading, and managing plugins."""

import importlib.util
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from .plugin_base import (
    PluginBase,
    TriggerPlugin,
    ToolPlugin,
    PluginEvent,
    TrayMenuItem,
)
from .models import ToolResult

if TYPE_CHECKING:
    from .event_bus import EventBus, Topics

logger = logging.getLogger(__name__)


@dataclass
class PluginError:
    """Record of a plugin error."""
    plugin_id: str
    plugin_name: str
    error_type: str  # "load", "initialize", "start", "execute"
    error_message: str
    timestamp: datetime
    fatal: bool  # If True, plugin is disabled


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, plugins_dir: Path, event_bus: "EventBus | None" = None):
        """Initialize plugin manager.

        Args:
            plugins_dir: Directory containing plugins
            event_bus: Optional EventBus for decoupled communication.
                      If provided, events will be published to the bus.
                      If None, old callback mechanism is used.
        """
        self.plugins_dir = plugins_dir
        self.triggers_dir = plugins_dir / "triggers"
        self.tools_dir = plugins_dir / "tools"

        self._triggers: dict[str, TriggerPlugin] = {}
        self._tools: dict[str, ToolPlugin] = {}
        self._tool_handlers: dict[str, ToolPlugin] = {}
        self._event_handlers: list[Callable[[PluginEvent], None]] = []
        self._plugin_errors: list[PluginError] = []
        self._event_bus = event_bus

    def on_event(self, handler: Callable[[PluginEvent], None]) -> None:
        """Register a global event handler for all plugin events.

        Note: Only used when EventBus is not provided (backward compatibility).
        """
        self._event_handlers.append(handler)

    def _handle_plugin_event(self, event: PluginEvent) -> None:
        """Forward plugin events to EventBus or registered handlers.

        If EventBus is available, publishes to PLUGIN_EVENT topic.
        Otherwise, calls registered callback handlers (backward compatibility).
        """
        # New approach: publish to EventBus
        if self._event_bus:
            from .event_bus import Topics
            self._event_bus.publish(Topics.PLUGIN_EVENT, event)
            return

        # Old approach: call handlers directly (backward compatibility)
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    def _record_error(
        self,
        plugin_id: str,
        plugin_name: str,
        error_type: str,
        error: Exception,
        fatal: bool = False
    ) -> None:
        """
        Record a plugin error for later inspection.

        Args:
            plugin_id: Plugin identifier
            plugin_name: Human-readable plugin name
            error_type: Type of error ("load", "initialize", "start", "execute")
            error: The exception that occurred
            fatal: If True, plugin is disabled and won't be loaded
        """
        plugin_error = PluginError(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            error_type=error_type,
            error_message=str(error),
            timestamp=datetime.now(),
            fatal=fatal
        )
        self._plugin_errors.append(plugin_error)

        if fatal:
            logger.error(
                f"Fatal error in plugin '{plugin_name}' ({error_type}): {error}"
            )
        else:
            logger.warning(
                f"Non-fatal error in plugin '{plugin_name}' ({error_type}): {error}"
            )

    def get_failed_plugins(self) -> dict[str, PluginError]:
        """
        Get plugins that failed fatally and are disabled.

        Returns:
            Dictionary mapping plugin_id to PluginError for fatal errors
        """
        return {
            err.plugin_id: err
            for err in self._plugin_errors
            if err.fatal
        }

    def get_all_errors(self) -> list[PluginError]:
        """
        Get all plugin errors (fatal and non-fatal).

        Returns:
            List of all PluginError records
        """
        return self._plugin_errors.copy()

    def discover_plugins(self) -> None:
        """Discover all available plugins in the plugins directory."""
        if self.triggers_dir.exists():
            for plugin_dir in self.triggers_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.py").exists():
                    self._load_trigger(plugin_dir)

        if self.tools_dir.exists():
            for plugin_dir in self.tools_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.py").exists():
                    self._load_tool(plugin_dir)

    def _load_trigger(self, plugin_dir: Path) -> None:
        """Load a trigger plugin from a directory."""
        plugin_id = plugin_dir.name
        try:
            plugin = self._load_plugin(plugin_dir, TriggerPlugin)
            if plugin and isinstance(plugin, TriggerPlugin):
                self._triggers[plugin.plugin_id] = plugin
                plugin.on_event(self._handle_plugin_event)
                logger.info(f"Loaded trigger plugin: {plugin.name}")
        except Exception as e:
            plugin_name = plugin_id.replace("_", " ").title()
            self._record_error(plugin_id, plugin_name, "load", e, fatal=True)
            logger.error(f"Failed to load trigger plugin from {plugin_dir}: {e}")

    def _load_tool(self, plugin_dir: Path) -> None:
        """Load a tool plugin from a directory."""
        plugin_id = plugin_dir.name
        try:
            plugin = self._load_plugin(plugin_dir, ToolPlugin)
            if plugin and isinstance(plugin, ToolPlugin):
                self._tools[plugin.plugin_id] = plugin
                # Register tool handlers
                logger.info(f"Loading tools for plugin: {plugin.name}")
                for tool_type in plugin.get_supported_tools():
                    logger.debug(f"\ttool type {tool_type}")
                    self._tool_handlers[tool_type] = plugin
        except Exception as e:
            plugin_name = plugin_id.replace("_", " ").title()
            self._record_error(plugin_id, plugin_name, "load", e, fatal=True)
            logger.error(f"Failed to load tool plugin from {plugin_dir}: {e}")

    def _load_plugin(self, plugin_dir: Path, expected_type: type) -> PluginBase | None:
        """Dynamically load a plugin module."""
        import sys

        plugin_file = plugin_dir / "plugin.py"
        category = plugin_dir.parent.name  # "triggers" or "tools"
        plugin_name = plugin_dir.name       # e.g. "system_info"

        # Register package hierarchy so relative imports work.
        # E.g. for "from .collectors.os_info import ..." in plugin.py,
        # Python needs "plugins.tools.system_info" as a package in sys.modules.
        for pkg_path, pkg_name in [
            (self.plugins_dir, "plugins"),
            (plugin_dir.parent, f"plugins.{category}"),
            (plugin_dir, f"plugins.{category}.{plugin_name}"),
        ]:
            if pkg_name not in sys.modules:
                init_file = pkg_path / "__init__.py"
                pkg_spec = importlib.util.spec_from_file_location(
                    pkg_name,
                    init_file if init_file.exists() else None,
                    submodule_search_locations=[str(pkg_path)],
                )
                if pkg_spec is not None:
                    pkg_mod = importlib.util.module_from_spec(pkg_spec)
                    sys.modules[pkg_name] = pkg_mod

        module_name = f"{pkg_name}.plugin"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find the plugin class
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, expected_type)
                and attr is not expected_type
                and attr is not PluginBase
                and attr is not TriggerPlugin
                and attr is not ToolPlugin
            ):
                plugin = attr(plugin_dir)
                plugin.load_config()
                return plugin

        return None

    async def initialize_all(self) -> None:
        """Initialize all loaded plugins."""
        for plugin in list(self._triggers.values()) + list(self._tools.values()):
            if plugin.enabled:
                try:
                    await plugin.initialize()
                    logger.info(f"Initialized plugin: {plugin.name}")
                except Exception as e:
                    self._record_error(
                        plugin.plugin_id,
                        plugin.name,
                        "initialize",
                        e,
                        fatal=False  # Non-fatal - plugin is loaded but not initialized
                    )
                    logger.error(f"Failed to initialize plugin {plugin.name}: {e}")

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        # Stop triggers first
        await self.stop_triggers()

        # Then shutdown all plugins
        for plugin in list(self._triggers.values()) + list(self._tools.values()):
            try:
                await plugin.shutdown()
                logger.info(f"Shutdown plugin: {plugin.name}")
            except Exception as e:
                logger.error(f"Failed to shutdown plugin {plugin.name}: {e}")

    async def start_triggers(self) -> None:
        """Start all trigger plugins."""
        for trigger in self._triggers.values():
            if trigger.enabled and not trigger.running:
                try:
                    await trigger.start()
                    logger.info(f"Started trigger: {trigger.name}")
                except Exception as e:
                    logger.error(f"Failed to start trigger {trigger.name}: {e}")

    async def stop_triggers(self) -> None:
        """Stop all trigger plugins."""
        for trigger in self._triggers.values():
            if trigger.running:
                try:
                    await trigger.stop()
                    logger.info(f"Stopped trigger: {trigger.name}")
                except Exception as e:
                    logger.error(f"Failed to stop trigger {trigger.name}: {e}")

    async def execute_tool(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        """Execute a tool by type."""
        handler = self._tool_handlers.get(tool_type)
        if handler is None:
            logger.warning(f"No handler found for tool type: {tool_type}")
            return ToolResult(success=False, error=f"No handler for {tool_type}")

        if not handler.enabled:
            logger.warning(f"Tool handler {handler.name} is disabled")
            return ToolResult(success=False, error=f"Handler {handler.name} is disabled")

        try:
            return await handler.execute(tool_type, parameters)
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_type}: {e}")
            return ToolResult(success=False, error=str(e))

    def get_all_tray_items(
        self,
        on_plugin_click: Callable[["PluginBase"], None] | None = None
    ) -> list[TrayMenuItem]:
        """Collect tray menu items for all plugins."""
        items: list[TrayMenuItem] = []

        # Triggers section
        trigger_items = []
        for trigger in self._triggers.values():
            status = "Running" if trigger.running else "Stopped"
            has_window = trigger.has_window()

            item = TrayMenuItem(
                id=f"trigger_{trigger.plugin_id}",
                label=f"{trigger.name}: {status}",
                callback=(
                    (lambda checked=False, t=trigger: on_plugin_click(t))
                    if on_plugin_click and has_window else None
                )
            )
            trigger_items.append(item)

        if trigger_items:
            items.append(TrayMenuItem(
                id="triggers",
                label="Triggers",
                children=trigger_items
            ))

        # Tools section
        tool_items = []
        for tool in self._tools.values():
            status = "Enabled" if tool.enabled else "Disabled"
            has_window = tool.has_window()

            item = TrayMenuItem(
                id=f"tool_{tool.plugin_id}",
                label=f"{tool.name}: {status}",
                callback=(
                    (lambda checked=False, a=tool: on_plugin_click(a))
                    if on_plugin_click and has_window else None
                )
            )
            tool_items.append(item)

        if tool_items:
            items.append(TrayMenuItem(
                id="tools",
                label="Tools",
                children=tool_items
            ))

        return items

    @property
    def triggers(self) -> dict[str, TriggerPlugin]:
        """Get all loaded trigger plugins."""
        return self._triggers.copy()

    @property
    def tools(self) -> dict[str, ToolPlugin]:
        """Get all loaded tool plugins."""
        return self._tools.copy()

    def get_capabilities(self) -> dict:
        """Get aggregated capabilities from all enabled plugins.

        Returns:
            Dict with 'triggers' and 'tools' keys, each mapping
            event/tool names to {"params": [...], "description": "..."} dicts.
        """
        triggers = {}
        for t in self._triggers.values():
            if t.enabled:
                for name, cap in t.get_capabilities().items():
                    triggers[name] = cap
        tools = {}
        for a in self._tools.values():
            if a.enabled:
                for name, cap in a.get_capabilities().items():
                    tools[name] = cap
        return {"triggers": triggers, "tools": tools}

    def get_supported_tool_types(self) -> list[str]:
        """Get all supported tool types."""
        return list(self._tool_handlers.keys())
