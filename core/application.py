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
from ui.tray import ConnectionStatus

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
        self._background_tasks: set[asyncio.Task] = set()

        # Subscribe to events
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to event bus topics."""
        # Plugin events -> Server
        self.event_bus.subscribe(Topics.PLUGIN_EVENT, self._handle_plugin_event)

        # Server actions -> Plugins
        self.event_bus.subscribe(Topics.SERVER_ACTION, self._handle_server_action)

        # Server status events
        self.event_bus.subscribe(Topics.SERVER_CONNECTED, self._handle_server_connected)
        self.event_bus.subscribe(Topics.SERVER_DISCONNECTED, self._handle_server_disconnected)
        self.event_bus.subscribe(Topics.SERVER_ERROR, self._handle_server_error)

        # UI events
        self.event_bus.subscribe(Topics.UI_QUIT_REQUESTED, self._handle_quit_request)
        self.event_bus.subscribe(Topics.UI_SETTINGS_REQUESTED, self._handle_settings_request)
        self.event_bus.subscribe(Topics.UI_SETTINGS_CHANGED, self._handle_settings_changed)

        # UI connection control events
        self.event_bus.subscribe(Topics.UI_CONNECT_REQUESTED, self._handle_connect_request)
        self.event_bus.subscribe(Topics.UI_DISCONNECT_REQUESTED, self._handle_disconnect_request)

        logger.debug("Subscribed to event bus topics")

    def _create_task(self, coro) -> asyncio.Task:
        """Create a background task with automatic cleanup.

        Prevents tasks from being garbage collected before completion.

        Args:
            coro: Coroutine to run as a task

        Returns:
            The created task
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

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
        self._create_task(self.server_client.send_trigger(payload))

    def _handle_server_action(self, action: ActionTask) -> None:
        """Handle server actions - execute via plugin manager.

        Args:
            action: Action task from server
        """
        logger.info(f"Received action from server: {action.type}")

        if self.plugin_manager:
            self._create_task(
                self.plugin_manager.execute_action(action.type, action.parameters)
            )

    def _handle_server_connected(self, data: None) -> None:
        """Handle server connected event.

        Args:
            data: Unused
        """
        logger.info("Server connected - updating tray")
        self.tray_manager.set_connection_status(ConnectionStatus.CONNECTED)

    def _handle_server_disconnected(self, data: None) -> None:
        """Handle server disconnected event.

        Args:
            data: Unused
        """
        logger.info("Server disconnected - updating tray")
        self.tray_manager.set_connection_status(ConnectionStatus.DISCONNECTED)

    def _handle_server_error(self, data: dict) -> None:
        """Handle server error event.

        Args:
            data: Error details (e.g., {"reason": "max_retries"})
        """
        logger.error(f"Server error - updating tray: {data}")
        self.tray_manager.set_connection_status(ConnectionStatus.ERROR)

    def _handle_connect_request(self, data: None) -> None:
        """Handle connect request from UI.

        Args:
            data: Unused
        """
        logger.info("Connect requested from UI")
        self.tray_manager.set_connection_status(ConnectionStatus.CONNECTING)
        self._create_task(self.server_client.connect())

    def _handle_disconnect_request(self, data: None) -> None:
        """Handle disconnect request from UI.

        Args:
            data: Unused
        """
        logger.info("Disconnect requested from UI")
        self._create_task(self.server_client.disconnect())

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
        self._create_task(self._shutdown())

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
        self._create_task(self._reconnect_server())

    async def _connect_with_linking(self) -> None:
        """Connect to server: link device first, then connect to Centrifugo.

        Flow:
        1. Check if device key is configured
        2. Try to link device with the server
        3. Only if linking succeeds, connect to Centrifugo WebSocket
        """
        device_key = self.config_manager.get("device_key", "")
        if not device_key:
            logger.warning("No device key configured, skipping server connection")
            self.tray_manager.set_connection_status(ConnectionStatus.DISCONNECTED)
            return

        self.tray_manager.set_connection_status(ConnectionStatus.CONNECTING)

        # Step 1: Link device
        capabilities = self.plugin_manager.get_capabilities() if self.plugin_manager else None
        linked = await self.server_client.link_device(
            device_os=self.device_info.get_platform(),
            device_name=self.device_info.get_hostname(),
            capabilities=capabilities,
        )
        if not linked:
            logger.error("Device linking failed, not connecting to Centrifugo")
            self.tray_manager.set_connection_status(ConnectionStatus.ERROR)
            return

        self.config_manager.set("device_linked", True)
        self.config_manager.save()

        # Step 2: Connect to Centrifugo
        await self.server_client.connect()

    async def _reconnect_server(self) -> None:
        """Reconnect to server with new settings."""
        await self.server_client.close()

        # Create new server client with updated config
        from .server_client import ServerClient

        self.server_client = ServerClient(
            server_url=self.config_manager.get("server_url", ""),
            device_key=self.config_manager.get("device_key", ""),
            device_id=self.device_info.device_id,
            reconnect_interval=self.config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS),
            event_bus=self.event_bus
        )

        if self.config_manager.get("auto_connect", True):
            await self._connect_with_linking()

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
                if not window.isVisible():
                    window.finished.connect(self._update_tray_menu)
                    window.show()
                window.raise_()
                window.activateWindow()

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

        # Set initial connection status
        self.tray_manager.set_connection_status(ConnectionStatus.DISCONNECTED)

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
            await self._connect_with_linking()

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
