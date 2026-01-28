#!/usr/bin/env python3
"""Main entry point for System Agent."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path before imports
if not getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(__file__).parent
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from core.config_manager import ConfigManager
from core.paths import get_app_dir, get_data_dir, get_plugins_dir
from core.device_info import DeviceInfo
from core.plugin_manager import PluginManager
from core.plugin_base import PluginEvent
from core.server_client import ServerClient
from core.models import TriggerPayload, ActionTask
from core.constants import APP_NAME, DEFAULT_RECONNECT_INTERVAL_MS
from ui.tray import TrayManager
from ui.settings import SettingsWindow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SystemAgent:
    """Main application class."""

    def __init__(self):
        self.app: QApplication | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.config_manager: ConfigManager | None = None
        self.device_info: DeviceInfo | None = None
        self.plugin_manager: PluginManager | None = None
        self.tray_manager: TrayManager | None = None
        self.server_client: ServerClient | None = None
        self._running = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing System Agent...")

        # Paths (support both bundled and script modes)
        app_dir = get_app_dir()
        data_dir = get_data_dir()
        plugins_dir = get_plugins_dir()
        assets_dir = app_dir / "assets"

        # Load configuration (stored in user data directory)
        self.config_manager = ConfigManager(data_dir / "config.json")
        self.config_manager.load()

        # Set log level from config
        log_level = self.config_manager.get("log_level", "INFO")
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

        # Initialize device info (stored in user data directory)
        self.device_info = DeviceInfo(data_dir)
        logger.info(f"Device ID: {self.device_info.device_id}")
        logger.info(f"Platform: {self.device_info.get_platform()}")

        # Store device_id in config if not set
        if not self.config_manager.device_id:
            self.config_manager.device_id = self.device_info.device_id
            self.config_manager.save()

        # Initialize plugin manager (non-critical - continue without plugins on failure)
        try:
            self.plugin_manager = PluginManager(plugins_dir)
            self.plugin_manager.on_event(self._handle_plugin_event)
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

        # Initialize server client
        self.server_client = ServerClient(
            server_url=self.config_manager.get("server_url", ""),
            api_key=self.config_manager.get("api_key", ""),
            device_id=self.device_info.device_id,
            reconnect_interval=self.config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS)
        )
        self.server_client.on_action(self._handle_server_action)

        # Initialize tray manager
        self.tray_manager = TrayManager(self.app, assets_dir)
        self.tray_manager.on_quit_requested(self._on_quit)
        self.tray_manager.on_settings_requested(self._on_settings)

        # Set tray icon for notification plugin
        self._setup_notification_plugin()

        # Update tray menu with plugin items
        self._update_tray_menu()

        # Show tray icon
        self.tray_manager.show()

        logger.info("System Agent initialized")

    def _setup_notification_plugin(self) -> None:
        """Set up the notification plugin with the tray manager."""
        if self.plugin_manager and self.tray_manager:
            for action in self.plugin_manager.actions.values():
                if hasattr(action, "set_tray_manager"):
                    action.set_tray_manager(self.tray_manager)

    def _update_tray_menu(self) -> None:
        """Update the tray menu with plugin items."""
        if self.plugin_manager and self.tray_manager:
            items = self.plugin_manager.get_all_tray_items(
                on_plugin_click=self._on_plugin_click
            )
            self.tray_manager.set_plugin_items(items)

    def _on_plugin_click(self, plugin) -> None:
        """Handle click on a plugin in the tray menu - open plugin window."""
        if plugin.has_window():
            window = plugin.create_window()
            if window:
                window.exec()
                # Refresh tray menu after window closes (status may have changed)
                self._update_tray_menu()

    def _handle_plugin_event(self, event: PluginEvent) -> None:
        """Handle events from plugins - send to server."""
        logger.info(f"Plugin event: {event.event_name} from {event.plugin_id}")
        logger.debug(f"Event data: {event.data}")

        # Send trigger to server
        if self.server_client and self.device_info:
            payload = TriggerPayload(
                name=event.event_name,
                data=event.data,
                device_id=self.device_info.device_id
            )
            asyncio.create_task(self.server_client.send_trigger(payload))

    def _handle_server_action(self, action: ActionTask) -> None:
        """Handle action received from server."""
        logger.info(f"Received action from server: {action.type}")

        # Execute action via plugin manager
        if self.plugin_manager:
            asyncio.create_task(
                self.plugin_manager.execute_action(action.type, action.parameters)
            )

    def _on_settings(self) -> None:
        """Handle settings request - open settings window."""
        logger.info("Opening settings window")
        if self.config_manager and self.plugin_manager and self.device_info:
            settings_window = SettingsWindow(
                config_manager=self.config_manager,
                plugin_manager=self.plugin_manager,
                device_info=self.device_info
            )
            settings_window.settings_changed.connect(self._on_settings_changed)
            settings_window.exec()

    def _on_settings_changed(self) -> None:
        """Handle settings changed - reload configuration."""
        logger.info("Settings changed, reloading...")
        if self.config_manager:
            self.config_manager.load()
            # Update log level
            log_level = self.config_manager.get("log_level", "INFO")
            logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

            # Recreate server client with new settings
            if self.server_client and self.device_info:
                asyncio.create_task(self._reconnect_server())

    async def _reconnect_server(self) -> None:
        """Reconnect to server with new settings."""
        if self.server_client:
            await self.server_client.close()

        if self.config_manager and self.device_info:
            self.server_client = ServerClient(
                server_url=self.config_manager.get("server_url", ""),
                api_key=self.config_manager.get("api_key", ""),
                device_id=self.device_info.device_id,
                reconnect_interval=self.config_manager.get("reconnect_interval", DEFAULT_RECONNECT_INTERVAL_MS)
            )
            self.server_client.on_action(self._handle_server_action)

            if self.config_manager.get("auto_connect", True):
                await self.server_client.connect()

    def _on_quit(self) -> None:
        """Handle quit request."""
        logger.info("Quit requested")
        self._running = False
        if self.loop:
            self.loop.call_soon(self._do_quit)

    def _do_quit(self) -> None:
        """Perform the actual quit."""
        asyncio.create_task(self._shutdown())

    async def _shutdown(self) -> None:
        """Shutdown all components."""
        logger.info("Shutting down System Agent...")

        if self.tray_manager:
            self.tray_manager.hide()

        if self.server_client:
            await self.server_client.close()

        if self.plugin_manager:
            await self.plugin_manager.shutdown_all()

        if self.app:
            self.app.quit()

        logger.info("System Agent shutdown complete")

    async def run(self) -> None:
        """Run the application."""
        await self.initialize()

        # Start triggers
        if self.plugin_manager:
            await self.plugin_manager.start_triggers()

        # Connect to server (if configured)
        if self.server_client and self.config_manager:
            if self.config_manager.get("auto_connect", True):
                await self.server_client.connect()

        # Update tray menu AFTER triggers started (to show correct status)
        self._update_tray_menu()

        self._running = True
        logger.info("System Agent is running")

        # Keep running until quit is requested
        while self._running:
            await asyncio.sleep(0.1)


def main():
    """Main entry point."""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Create async event loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create and run the agent
    agent = SystemAgent()
    agent.app = app
    agent.loop = loop

    with loop:
        try:
            loop.run_until_complete(agent.run())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            loop.run_until_complete(agent._shutdown())


if __name__ == "__main__":
    main()
