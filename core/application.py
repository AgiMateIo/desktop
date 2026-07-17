"""Application coordinator using dependency injection and event bus."""

import asyncio
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .protocols import IConfigManager, IDeviceInfo, IPluginManager, IServerClient, ITrayManager
from .event_bus import EventBus, Topics
from .plugin_base import PluginEvent
from .models import TriggerPayload, ToolTask, ToolResult
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
        loop: asyncio.AbstractEventLoop,
        mcp_server=None,
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
            mcp_server: MCP server manager (None if disabled)
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
        self.mcp_server = mcp_server

        self._running = False
        self._background_tasks: set[asyncio.Task] = set()
        self._settings_window: SettingsWindow | None = None

        # Subscribe to events
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to event bus topics."""
        # Plugin events -> Server
        self.event_bus.subscribe(Topics.PLUGIN_EVENT, self._handle_plugin_event)

        # Plugin capabilities changed -> re-link device catalog
        self.event_bus.subscribe(
            Topics.PLUGIN_CAPABILITIES_CHANGED, self._handle_capabilities_changed
        )

        # Server tools -> Plugins
        self.event_bus.subscribe(Topics.TOOL_CALL_RECEIVED, self._handle_tool_call)

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

        # MCP trigger buffering (separate from backend pathway)
        if self.mcp_server:
            self.event_bus.subscribe(Topics.PLUGIN_EVENT, self.mcp_server.on_trigger)

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

    def _handle_tool_call(self, tool: ToolTask) -> None:
        """Handle tool calls - execute via plugin manager and send result back.

        Args:
            tool: Tool task from server
        """
        logger.info(f"Executing tool '{tool.name}' (id={tool.id})")

        if self.plugin_manager:
            self._create_task(self._execute_and_report(tool))

    async def _execute_and_report(self, tool: ToolTask) -> None:
        """Execute a tool and send the result back to the server.

        Args:
            tool: Tool task from server
        """
        result = await self.plugin_manager.execute_tool(tool.name, tool.params)

        if result.success and result.file:
            output, error = await self._upload_result_file(tool, result)
        elif result.success:
            output = json.dumps(result.data or {"status": "ok"}, ensure_ascii=False)
            error = None
            logger.info(f"Tool '{tool.name}' succeeded (id={tool.id})")
        else:
            output = None
            error = result.error or "Tool execution failed"
            logger.warning(f"Tool '{tool.name}' failed (id={tool.id}): {error}")

        # Echo the server-issued tool call ID back as-is (opaque string)
        await self.server_client.send_tool_result(
            tool.id,
            output=output,
            error=error,
            connector_code=tool.connector_code,
        )

    async def _upload_result_file(self, tool: ToolTask, result: ToolResult) -> tuple[str | None, str | None]:
        """Upload a tool's binary attachment and build the file-reference output.

        Binary results are uploaded via POST /control/app/files; the tool
        output carries only a compact {"file": {id, mime, size}} reference
        (the "file" key and agf_<uuid> id format are part of the contract).

        Returns:
            (output, error) tuple for send_tool_result.
        """
        attachment = result.file
        info, upload_error = await self.server_client.upload_file(
            attachment.data, attachment.filename, attachment.mime
        )

        if info is None:
            logger.warning(
                f"Tool '{tool.name}' file upload failed (id={tool.id}): {upload_error}"
            )
            return None, upload_error

        data = dict(result.data or {})
        data["file"] = {
            "id": info.get("id"),
            "mime": info.get("mime", attachment.mime),
            "size": info.get("size", len(attachment.data)),
        }
        logger.info(f"Tool '{tool.name}' succeeded with file {info.get('id')} (id={tool.id})")
        return json.dumps(data, ensure_ascii=False), None

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
        reason = data.get("reason", "unknown") if isinstance(data, dict) else data
        logger.error(f"Server error - updating tray (reason: {reason})")
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

        # Reconnect backend server with new settings (only if enabled)
        backend_enabled = self.config_manager.get("backend", "enabled") == "enabled"
        if backend_enabled:
            self._create_task(self._reconnect_server())
        else:
            self._create_task(self.server_client.close())

    async def _link_device(self) -> bool:
        """Link device with the server, declaring the full plugin catalog.

        The link call fully replaces the device catalog (triggers + tools),
        and the server rejects triggers that were not declared here.

        Returns:
            True if linking succeeded, False otherwise.
        """
        capabilities = self.plugin_manager.get_capabilities() if self.plugin_manager else None
        system_info = self.device_info.get_system_info()
        device_features = {
            "appVersion": "1.0.0",
            "arch": system_info.get("machine", ""),
            "osVersion": system_info.get("release", ""),
            "pythonVersion": system_info.get("python_version", ""),
        }
        return await self.server_client.link_device(
            device_os=self.device_info.get_platform(),
            device_name=self.device_info.get_hostname(),
            capabilities=capabilities,
            device_features=device_features,
        )

    def _handle_capabilities_changed(self, plugin_id: str) -> None:
        """Handle plugin capabilities change - re-declare catalog with the server.

        Args:
            plugin_id: ID of the plugin whose config was saved
        """
        backend_enabled = self.config_manager.get("backend", "enabled") == "enabled"
        device_key = self.config_manager.get("device_key", "")
        if not backend_enabled or not device_key:
            return

        logger.info(f"Plugin '{plugin_id}' capabilities changed, re-linking device")
        self._create_task(self._link_device())

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
        linked = await self._link_device()
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
            for tool in self.plugin_manager.tools.values():
                if hasattr(tool, "set_tray_manager"):
                    tool.set_tray_manager(self.tray_manager)

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

        # Start MCP server (independent of backend)
        if self.mcp_server:
            await self.mcp_server.start()

        # Connect to backend server (only if enabled)
        backend_enabled = self.config_manager.get("backend", "enabled") == "enabled"
        if backend_enabled and self.config_manager.get("auto_connect", True):
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

        if self.mcp_server:
            await self.mcp_server.stop()

        await self.server_client.close()

        if self.plugin_manager:
            await self.plugin_manager.shutdown_all()

        self.app.quit()

        logger.info("Application shutdown complete")
