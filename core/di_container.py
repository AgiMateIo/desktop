"""Dependency injection container for managing component lifecycles."""

import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtWidgets import QApplication

from .config_manager import ConfigManager
from .device_info import DeviceInfo
from .plugin_manager import PluginManager
from .server_client import ServerClient
from .event_bus import EventBus
from .constants import DEFAULT_RECONNECT_INTERVAL_MS, DEFAULT_MCP_PORT
from .paths import get_app_dir, get_data_dir, get_plugins_dir
from ui.tray import TrayManager

logger = logging.getLogger(__name__)


class DIContainer:
    """Simple dependency injection container.

    Manages singleton instances and factory functions for creating components.
    """

    def __init__(self):
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}

    def register_singleton(self, name: str, instance: Any) -> None:
        """Register a singleton instance.

        Args:
            name: Component name
            instance: Component instance
        """
        self._singletons[name] = instance
        logger.debug(f"Registered singleton: {name}")

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a factory function.

        Args:
            name: Component name
            factory: Factory function that creates the component
        """
        self._factories[name] = factory
        logger.debug(f"Registered factory: {name}")

    def get(self, name: str) -> Any:
        """Get a component by name.

        Args:
            name: Component name

        Returns:
            Component instance

        Raises:
            KeyError: If component not found
        """
        # Try singleton first
        if name in self._singletons:
            return self._singletons[name]

        # Try factory
        if name in self._factories:
            instance = self._factories[name]()
            # Cache singleton after creation
            self._singletons[name] = instance
            return instance

        raise KeyError(f"Component '{name}' not found in container")

    def has(self, name: str) -> bool:
        """Check if component exists.

        Args:
            name: Component name

        Returns:
            True if component is registered
        """
        return name in self._singletons or name in self._factories


class ContainerBuilder:
    """Builder for configuring the DI container."""

    @staticmethod
    def build_container(app: QApplication, loop) -> DIContainer:
        """Build and configure the DI container.

        Args:
            app: Qt application instance
            loop: asyncio event loop

        Returns:
            Configured DI container
        """
        container = DIContainer()

        # Paths
        app_dir = get_app_dir()
        data_dir = get_data_dir()
        plugins_dir = get_plugins_dir()
        assets_dir = app_dir / "assets"

        # Register paths as singletons
        container.register_singleton("app_dir", app_dir)
        container.register_singleton("data_dir", data_dir)
        container.register_singleton("plugins_dir", plugins_dir)
        container.register_singleton("assets_dir", assets_dir)

        # Register Qt components
        container.register_singleton("app", app)
        container.register_singleton("loop", loop)

        # Register EventBus (core coordination layer)
        event_bus = EventBus()
        container.register_singleton("event_bus", event_bus)

        # Register ConfigManager factory
        def create_config_manager() -> ConfigManager:
            config_path = data_dir / "config.json"
            config_manager = ConfigManager(config_path)
            config_manager.load()

            # Set log level from config
            log_level = config_manager.get("log_level", "INFO")
            logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

            return config_manager

        container.register_factory("config_manager", create_config_manager)

        # Register DeviceInfo factory
        def create_device_info() -> DeviceInfo:
            config_manager = container.get("config_manager")
            device_info = DeviceInfo(config_manager)
            logger.info(f"Device ID: {device_info.device_id}")
            logger.info(f"Platform: {device_info.get_platform()}")
            return device_info

        container.register_factory("device_info", create_device_info)

        # Register PluginManager factory
        def create_plugin_manager() -> PluginManager | None:
            try:
                plugin_manager = PluginManager(plugins_dir, event_bus=event_bus)
                return plugin_manager
            except Exception as e:
                logger.error(f"Failed to create plugin manager: {e}")
                return None

        container.register_factory("plugin_manager", create_plugin_manager)

        # Register ServerClient factory
        def create_server_client() -> ServerClient:
            config_manager = container.get("config_manager")
            device_info = container.get("device_info")

            server_client = ServerClient(
                server_url=config_manager.get("server_url", ""),
                device_key=config_manager.get("device_key", ""),
                device_id=device_info.device_id,
                reconnect_interval=config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS),
                event_bus=event_bus
            )
            return server_client

        container.register_factory("server_client", create_server_client)

        # Register MCPServerManager factory
        def create_mcp_server():
            config_manager = container.get("config_manager")

            if config_manager.get("mcp_server", "disabled") != "enabled":
                logger.info("MCP server disabled in config")
                return None

            plugin_manager = container.get("plugin_manager")
            if plugin_manager is None:
                logger.warning("No plugin manager, MCP server cannot expose tools")
                return None

            from .mcp_server import MCPServerManager

            port = config_manager.get("mcp_port", DEFAULT_MCP_PORT)
            return MCPServerManager(plugin_manager=plugin_manager, port=port)

        container.register_factory("mcp_server", create_mcp_server)

        # Register TrayManager factory
        def create_tray_manager() -> TrayManager:
            return TrayManager(app, assets_dir, event_bus=event_bus)

        container.register_factory("tray_manager", create_tray_manager)

        logger.info("DI container configured")
        return container
