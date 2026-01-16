"""Plugin manager for discovering, loading, and managing plugins."""

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable

from .plugin_base import (
    PluginBase,
    TriggerPlugin,
    ActionPlugin,
    PluginEvent,
    TrayMenuItem,
)

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self.triggers_dir = plugins_dir / "triggers"
        self.actions_dir = plugins_dir / "actions"

        self._triggers: dict[str, TriggerPlugin] = {}
        self._actions: dict[str, ActionPlugin] = {}
        self._action_handlers: dict[str, ActionPlugin] = {}
        self._event_handlers: list[Callable[[PluginEvent], None]] = []

    def on_event(self, handler: Callable[[PluginEvent], None]) -> None:
        """Register a global event handler for all plugin events."""
        self._event_handlers.append(handler)

    def _handle_plugin_event(self, event: PluginEvent) -> None:
        """Forward plugin events to all registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    def discover_plugins(self) -> None:
        """Discover all available plugins in the plugins directory."""
        if self.triggers_dir.exists():
            for plugin_dir in self.triggers_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.py").exists():
                    self._load_trigger(plugin_dir)

        if self.actions_dir.exists():
            for plugin_dir in self.actions_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "plugin.py").exists():
                    self._load_action(plugin_dir)

    def _load_trigger(self, plugin_dir: Path) -> None:
        """Load a trigger plugin from a directory."""
        try:
            plugin = self._load_plugin(plugin_dir, TriggerPlugin)
            if plugin and isinstance(plugin, TriggerPlugin):
                self._triggers[plugin.plugin_id] = plugin
                plugin.on_event(self._handle_plugin_event)
                logger.info(f"Loaded trigger plugin: {plugin.name}")
        except Exception as e:
            logger.error(f"Failed to load trigger plugin from {plugin_dir}: {e}")

    def _load_action(self, plugin_dir: Path) -> None:
        """Load an action plugin from a directory."""
        try:
            plugin = self._load_plugin(plugin_dir, ActionPlugin)
            if plugin and isinstance(plugin, ActionPlugin):
                self._actions[plugin.plugin_id] = plugin
                # Register action handlers
                logger.info(f"Loading actions for plugin: {plugin.name}")
                for action_type in plugin.get_supported_actions():
                    logger.debug(f"\taction type {action_type}")
                    self._action_handlers[action_type] = plugin
        except Exception as e:
            logger.error(f"Failed to load action plugin from {plugin_dir}: {e}")

    def _load_plugin(self, plugin_dir: Path, expected_type: type) -> PluginBase | None:
        """Dynamically load a plugin module."""
        plugin_file = plugin_dir / "plugin.py"

        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_dir.parent.name}.{plugin_dir.name}",
            plugin_file
        )
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
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
                and attr is not ActionPlugin
            ):
                plugin = attr(plugin_dir)
                plugin.load_config()
                return plugin

        return None

    async def initialize_all(self) -> None:
        """Initialize all loaded plugins."""
        for plugin in list(self._triggers.values()) + list(self._actions.values()):
            if plugin.enabled:
                try:
                    await plugin.initialize()
                    logger.info(f"Initialized plugin: {plugin.name}")
                except Exception as e:
                    logger.error(f"Failed to initialize plugin {plugin.name}: {e}")

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        # Stop triggers first
        await self.stop_triggers()

        # Then shutdown all plugins
        for plugin in list(self._triggers.values()) + list(self._actions.values()):
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

    async def execute_action(self, action_type: str, parameters: dict[str, Any]) -> bool:
        """Execute an action by type."""
        handler = self._action_handlers.get(action_type)
        if handler is None:
            logger.warning(f"No handler found for action type: {action_type}")
            return False

        if not handler.enabled:
            logger.warning(f"Action handler {handler.name} is disabled")
            return False

        try:
            return await handler.execute(action_type, parameters)
        except Exception as e:
            logger.error(f"Failed to execute action {action_type}: {e}")
            return False

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

        # Actions section
        action_items = []
        for action in self._actions.values():
            status = "Enabled" if action.enabled else "Disabled"
            has_window = action.has_window()

            item = TrayMenuItem(
                id=f"action_{action.plugin_id}",
                label=f"{action.name}: {status}",
                callback=(
                    (lambda checked=False, a=action: on_plugin_click(a))
                    if on_plugin_click and has_window else None
                )
            )
            action_items.append(item)

        if action_items:
            items.append(TrayMenuItem(
                id="actions",
                label="Actions",
                children=action_items
            ))

        return items

    @property
    def triggers(self) -> dict[str, TriggerPlugin]:
        """Get all loaded trigger plugins."""
        return self._triggers.copy()

    @property
    def actions(self) -> dict[str, ActionPlugin]:
        """Get all loaded action plugins."""
        return self._actions.copy()

    def get_supported_action_types(self) -> list[str]:
        """Get all supported action types."""
        return list(self._action_handlers.keys())
