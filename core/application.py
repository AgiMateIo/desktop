"""Application coordinator using dependency injection and event bus."""

import asyncio
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .protocols import IConfigManager, IDeviceInfo, IPluginManager, IServerClient, ITrayManager
from .event_bus import EventBus, Topics
from .plugin_base import PluginEvent
from .models import TriggerPayload, ActionTask
from .constants import DEFAULT_RECONNECT_INTERVAL_MS
from ui.settings import SettingsWindow

logger = logging.getLogger(__name__)


class Application:
    """Application coordinator with dependency injection.

    Replaces SystemAgent god object by:
    - Receiving dependencies via constructor (not creating them)
    - Using EventBus for coordination (not direct callbacks)
    - Focusing on lifecycle management only
    """

    def __init__(
        self,
        config_manager: IConfigManager,
        device_info: IDeviceInfo,
        plugin_manager: IPluginManager | None,
        server_client: IServerClient,
        tray_manager: ITrayManager,
        event_bus: EventBus,
        app: QApplication,
        loop: asyncio.AbstractEventLoop
    ):
        """Initialize application with dependencies.

        Args:
            config_manager: Configuration manager
            device_info: Device information
            plugin_manager: Plugin manager (can be None if plugins failed)
            server_client: Server client
            tray_manager: Tray manager
            event_bus: Event bus for coordination
            app: Qt application
            loop: asyncio event loop
        """
        # Inject dependencies
        self.config_manager = config_manager
        self.device_info = device_info
        self.plugin_manager = plugin_manager
        self.server_client = server_client
        self.tray_manager = tray_manager
        self.event_bus = event_bus
        self.app = app
        self.loop = loop

        self._running = False

        # Subscribe to events
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to event bus topics."""
        # Plugin events -> Server
        self.event_bus.subscribe(Topics.PLUGIN_EVENT, self._handle_plugin_event)

        # Server actions -> Plugins
        self.event_bus.subscribe(Topics.SERVER_ACTION, self._handle_server_action)

        # UI events
        self.event_bus.subscribe(Topics.UI_QUIT_REQUESTED, self._handle_quit_request)
        self.event_bus.subscribe(Topics.UI_SETTINGS_REQUESTED, self._handle_settings_request)
        self.event_bus.subscribe(Topics.UI_SETTINGS_CHANGED, self._handle_settings_changed)

        logger.debug("Subscribed to event bus topics")

    # Event handlers

    def _handle_plugin_event(self, event: PluginEvent) -> None:
        """Handle plugin events - send triggers to server.

        Args:
            event: Plugin event
        """
        logger.info(f"Plugin event: {event.event_name} from {event.plugin_id}")
        logger.debug(f"Event data: {event.data}")

        # Send trigger to server
        payload = TriggerPayload(
            name=event.event_name,
            data=event.data,
            device_id=self.device_info.device_id
        )
        asyncio.create_task(self.server_client.send_trigger(payload))

    def _handle_server_action(self, action: ActionTask) -> None:
        """Handle server actions - execute via plugin manager.

        Args:
            action: Action task from server
        """
        logger.info(f"Received action from server: {action.type}")

        if self.plugin_manager:
            asyncio.create_task(
                self.plugin_manager.execute_action(action.type, action.parameters)
            )

    def _handle_quit_request(self, data: None) -> None:
        """Handle quit request from UI.

        Args:
            data: Unused
        """
        logger.info("Quit requested")
        self._running = False
        if self.loop:
            self.loop.call_soon(self._do_quit)

    def _do_quit(self) -> None:
        """Perform the actual quit."""
        asyncio.create_task(self._shutdown())

    def _handle_settings_request(self, data: None) -> None:
        """Handle settings request from UI.

        Args:
            data: Unused
        """
        logger.info("Opening settings window")

        settings_window = SettingsWindow(
            config_manager=self.config_manager,
            plugin_manager=self.plugin_manager,
            device_info=self.device_info
        )
        settings_window.settings_changed.connect(self._on_settings_changed_signal)
        settings_window.exec()

    def _on_settings_changed_signal(self) -> None:
        """Qt signal handler - publishes to event bus."""
        self.event_bus.publish(Topics.UI_SETTINGS_CHANGED, None)

    def _handle_settings_changed(self, data: None) -> None:
        """Handle settings changed - reload configuration.

        Args:
            data: Unused
        """
        logger.info("Settings changed, reloading...")
        self.config_manager.load()

        # Update log level
        log_level = self.config_manager.get("log_level", "INFO")
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

        # Reconnect server with new settings
        asyncio.create_task(self._reconnect_server())

    async def _reconnect_server(self) -> None:
        """Reconnect to server with new settings."""
        await self.server_client.close()

        # Create new server client with updated config
        from .server_client import ServerClient

        self.server_client = ServerClient(
            server_url=self.config_manager.get("server_url", ""),
            api_key=self.config_manager.get("api_key", ""),
            device_id=self.device_info.device_id,
            reconnect_interval=self.config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS),
            event_bus=self.event_bus
        )

        if self.config_manager.get("auto_connect", True):
            await self.server_client.connect()

    # Plugin coordination

    def _setup_notification_plugin(self) -> None:
        """Set up the notification plugin with the tray manager."""
        if self.plugin_manager:
            for action in self.plugin_manager.actions.values():
                if hasattr(action, "set_tray_manager"):
                    action.set_tray_manager(self.tray_manager)

    def _update_tray_menu(self) -> None:
        """Update the tray menu with plugin items."""
        if self.plugin_manager:
            items = self.plugin_manager.get_all_tray_items(
                on_plugin_click=self._on_plugin_click
            )
            self.tray_manager.set_plugin_items(items)

    def _on_plugin_click(self, plugin) -> None:
        """Handle click on a plugin in the tray menu - open plugin window.

        Args:
            plugin: Plugin instance
        """
        if plugin.has_window():
            window = plugin.create_window()
            if window:
                window.exec()
                # Refresh tray menu after window closes (status may have changed)
                self._update_tray_menu()

    # Lifecycle management

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing Application...")

        # Initialize plugin manager (non-critical - can be None)
        if self.plugin_manager:
            try:
                self.plugin_manager.discover_plugins()
                await self.plugin_manager.initialize_all()

                # Check for failed plugins
                failed_plugins = self.plugin_manager.get_failed_plugins()
                if failed_plugins:
                    logger.warning(
                        f"{len(failed_plugins)} plugin(s) failed to load: "
                        f"{', '.join(p.plugin_name for p in failed_plugins.values())}"
                    )
            except Exception as e:
                logger.error(f"Plugin manager initialization failed: {e}")
                logger.warning("Continuing without plugins")
                self.plugin_manager = None

        # Note: No need to register callbacks - components publish to EventBus directly

        # Set tray icon for notification plugin
        self._setup_notification_plugin()

        # Update tray menu with plugin items
        self._update_tray_menu()

        # Show tray icon
        self.tray_manager.show()

        logger.info("Application initialized")

    async def run(self) -> None:
        """Run the application."""
        await self.initialize()

        # Start triggers
        if self.plugin_manager:
            await self.plugin_manager.start_triggers()

        # Connect to server (if configured)
        if self.config_manager.get("auto_connect", True):
            await self.server_client.connect()

        # Update tray menu AFTER triggers started (to show correct status)
        self._update_tray_menu()

        self._running = True
        logger.info("Application is running")

        # Keep running until quit is requested
        while self._running:
            await asyncio.sleep(0.1)

    async def _shutdown(self) -> None:
        """Shutdown all components."""
        logger.info("Shutting down Application...")

        self.tray_manager.hide()

        await self.server_client.close()

        if self.plugin_manager:
            await self.plugin_manager.shutdown_all()

        self.app.quit()

        logger.info("Application shutdown complete")
