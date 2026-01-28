"""Tests for Application coordinator."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call

from core.application import Application
from core.event_bus import EventBus, Topics
from core.plugin_base import PluginEvent
from core.models import ActionTask


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for Application."""
    config_manager = MagicMock()
    config_manager.get.return_value = True
    config_manager.device_id = "test-device"

    device_info = MagicMock()
    device_info.device_id = "test-device"

    plugin_manager = MagicMock()
    plugin_manager.actions = {}
    plugin_manager.get_all_tray_items = MagicMock(return_value=[])
    plugin_manager.get_failed_plugins = MagicMock(return_value={})
    plugin_manager.discover_plugins = MagicMock()
    plugin_manager.initialize_all = AsyncMock()
    plugin_manager.start_triggers = AsyncMock()
    plugin_manager.shutdown_all = AsyncMock()
    plugin_manager.execute_action = AsyncMock()

    server_client = MagicMock()
    server_client.send_trigger = AsyncMock()
    server_client.connect = AsyncMock()
    server_client.close = AsyncMock()

    tray_manager = MagicMock()
    tray_manager.show = MagicMock()
    tray_manager.hide = MagicMock()
    tray_manager.set_plugin_items = MagicMock()

    event_bus = EventBus()

    app = MagicMock()
    app.quit = MagicMock()

    loop = MagicMock()

    return {
        "config_manager": config_manager,
        "device_info": device_info,
        "plugin_manager": plugin_manager,
        "server_client": server_client,
        "tray_manager": tray_manager,
        "event_bus": event_bus,
        "app": app,
        "loop": loop
    }


class TestApplicationInit:
    """Tests for Application initialization."""

    def test_init(self, mock_dependencies):
        """Test Application initialization."""
        application = Application(**mock_dependencies)

        assert application.config_manager is mock_dependencies["config_manager"]
        assert application.device_info is mock_dependencies["device_info"]
        assert application.plugin_manager is mock_dependencies["plugin_manager"]
        assert application.server_client is mock_dependencies["server_client"]
        assert application.tray_manager is mock_dependencies["tray_manager"]
        assert application.event_bus is mock_dependencies["event_bus"]
        assert application.app is mock_dependencies["app"]
        assert application.loop is mock_dependencies["loop"]

    def test_subscribes_to_events(self, mock_dependencies):
        """Test that Application subscribes to event bus topics."""
        event_bus = mock_dependencies["event_bus"]
        application = Application(**mock_dependencies)

        # Check that handlers are registered
        assert Topics.PLUGIN_EVENT in event_bus._sync_handlers
        assert Topics.SERVER_ACTION in event_bus._sync_handlers
        assert Topics.UI_QUIT_REQUESTED in event_bus._sync_handlers
        assert Topics.UI_SETTINGS_REQUESTED in event_bus._sync_handlers
        assert Topics.UI_SETTINGS_CHANGED in event_bus._sync_handlers


class TestApplicationEventHandling:
    """Tests for Application event handling."""

    def test_handle_plugin_event(self, mock_dependencies):
        """Test handling plugin events."""
        application = Application(**mock_dependencies)

        plugin_event = PluginEvent(
            plugin_id="test-plugin",
            event_name="test.event",
            data={"key": "value"}
        )

        # Publish event
        application.event_bus.publish(Topics.PLUGIN_EVENT, plugin_event)

        # Should call send_trigger
        mock_dependencies["server_client"].send_trigger.assert_called_once()

    def test_handle_server_action(self, mock_dependencies):
        """Test handling server actions."""
        application = Application(**mock_dependencies)

        action = ActionTask(
            type="TEST_ACTION",
            parameters={"key": "value"}
        )

        # Publish event
        application.event_bus.publish(Topics.SERVER_ACTION, action)

        # Should call execute_action
        mock_dependencies["plugin_manager"].execute_action.assert_called_once()

    def test_handle_quit_request(self, mock_dependencies):
        """Test handling quit request."""
        application = Application(**mock_dependencies)
        application._running = True

        # Mock loop.call_soon
        call_soon_mock = MagicMock()
        application.loop.call_soon = call_soon_mock

        # Publish event
        application.event_bus.publish(Topics.UI_QUIT_REQUESTED, None)

        # Should stop running and call quit
        assert application._running is False
        call_soon_mock.assert_called_once()

    def test_handle_settings_request(self, mock_dependencies):
        """Test handling settings request."""
        application = Application(**mock_dependencies)

        with patch("core.application.SettingsWindow") as MockSettingsWindow:
            mock_window = MagicMock()
            MockSettingsWindow.return_value = mock_window

            # Publish event
            application.event_bus.publish(Topics.UI_SETTINGS_REQUESTED, None)

            # Should create and show settings window
            MockSettingsWindow.assert_called_once()
            mock_window.exec.assert_called_once()

    def test_handle_settings_changed(self, mock_dependencies):
        """Test handling settings changed."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.UI_SETTINGS_CHANGED, None)

        # Should reload config
        mock_dependencies["config_manager"].load.assert_called_once()


class TestApplicationLifecycle:
    """Tests for Application lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_dependencies):
        """Test Application initialization."""
        application = Application(**mock_dependencies)

        await application.initialize()

        # Should initialize plugin manager
        mock_dependencies["plugin_manager"].discover_plugins.assert_called_once()
        mock_dependencies["plugin_manager"].initialize_all.assert_called_once()

        # Should show tray
        mock_dependencies["tray_manager"].show.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_plugins(self, mock_dependencies):
        """Test initialization without plugin manager."""
        mock_dependencies["plugin_manager"] = None
        application = Application(**mock_dependencies)

        # Should not raise exception
        await application.initialize()

        # Should still show tray
        mock_dependencies["tray_manager"].show.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_plugin_failure(self, mock_dependencies):
        """Test initialization with plugin failures."""
        mock_dependencies["plugin_manager"].initialize_all.side_effect = Exception("Plugin error")

        application = Application(**mock_dependencies)
        await application.initialize()

        # Should handle error gracefully
        assert application.plugin_manager is None

    @pytest.mark.asyncio
    async def test_run_starts_triggers(self, mock_dependencies):
        """Test that run starts triggers."""
        application = Application(**mock_dependencies)

        # Patch initialize and asyncio.sleep to exit immediately
        with patch.object(application, "initialize", new_callable=AsyncMock), \
             patch("asyncio.sleep", side_effect=[None, Exception("Exit loop")]):
            try:
                await application.run()
            except Exception as e:
                if str(e) != "Exit loop":
                    raise

            # Should start triggers
            mock_dependencies["plugin_manager"].start_triggers.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_connects_to_server(self, mock_dependencies):
        """Test that run connects to server."""
        mock_dependencies["config_manager"].get.return_value = True  # auto_connect

        application = Application(**mock_dependencies)

        # Patch initialize and asyncio.sleep to exit immediately
        with patch.object(application, "initialize", new_callable=AsyncMock), \
             patch("asyncio.sleep", side_effect=[None, Exception("Exit loop")]):
            try:
                await application.run()
            except Exception as e:
                if str(e) != "Exit loop":
                    raise

            # Should connect to server
            mock_dependencies["server_client"].connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_dependencies):
        """Test Application shutdown."""
        application = Application(**mock_dependencies)

        await application._shutdown()

        # Should hide tray
        mock_dependencies["tray_manager"].hide.assert_called_once()

        # Should close server
        mock_dependencies["server_client"].close.assert_called_once()

        # Should shutdown plugins
        mock_dependencies["plugin_manager"].shutdown_all.assert_called_once()

        # Should quit app
        mock_dependencies["app"].quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_without_plugins(self, mock_dependencies):
        """Test shutdown without plugin manager."""
        mock_dependencies["plugin_manager"] = None
        application = Application(**mock_dependencies)

        # Should not raise exception
        await application._shutdown()

        # Should still quit app
        mock_dependencies["app"].quit.assert_called_once()


class TestApplicationPluginCoordination:
    """Tests for Application plugin coordination."""

    def test_setup_notification_plugin(self, mock_dependencies):
        """Test setting up notification plugin."""
        # Create mock action with set_tray_manager
        mock_action = MagicMock()
        mock_action.set_tray_manager = MagicMock()

        mock_dependencies["plugin_manager"].actions = {"notification": mock_action}

        application = Application(**mock_dependencies)
        application._setup_notification_plugin()

        # Should call set_tray_manager
        mock_action.set_tray_manager.assert_called_once_with(
            mock_dependencies["tray_manager"]
        )

    def test_update_tray_menu(self, mock_dependencies):
        """Test updating tray menu."""
        mock_items = [MagicMock(), MagicMock()]
        mock_dependencies["plugin_manager"].get_all_tray_items.return_value = mock_items

        application = Application(**mock_dependencies)
        application._update_tray_menu()

        # Should get items and set them
        mock_dependencies["plugin_manager"].get_all_tray_items.assert_called_once()
        mock_dependencies["tray_manager"].set_plugin_items.assert_called_once_with(mock_items)

    def test_on_plugin_click(self, mock_dependencies):
        """Test handling plugin click."""
        mock_plugin = MagicMock()
        mock_plugin.has_window.return_value = True

        mock_window = MagicMock()
        mock_plugin.create_window.return_value = mock_window

        application = Application(**mock_dependencies)
        application._on_plugin_click(mock_plugin)

        # Should create and show window
        mock_plugin.create_window.assert_called_once()
        mock_window.exec.assert_called_once()

    def test_on_plugin_click_no_window(self, mock_dependencies):
        """Test handling plugin click when plugin has no window."""
        mock_plugin = MagicMock()
        mock_plugin.has_window.return_value = False

        application = Application(**mock_dependencies)
        application._on_plugin_click(mock_plugin)

        # Should not create window
        mock_plugin.create_window.assert_not_called()


class TestApplicationServerReconnect:
    """Tests for server reconnection."""

    @pytest.mark.asyncio
    async def test_reconnect_server(self, mock_dependencies):
        """Test reconnecting to server."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "server_url": "http://new-server.com",
            "api_key": "new-key",
            "reconnect_interval": 5000,
            "auto_connect": True
        }.get(key, default)

        application = Application(**mock_dependencies)

        with patch("core.server_client.ServerClient") as MockServerClient:
            mock_new_client = MagicMock()
            mock_new_client.connect = AsyncMock()
            mock_new_client.on_action = MagicMock()
            MockServerClient.return_value = mock_new_client

            await application._reconnect_server()

            # Should close old client
            mock_dependencies["server_client"].close.assert_called_once()

            # Should create new client
            MockServerClient.assert_called_once()

            # Should connect if auto_connect
            mock_new_client.connect.assert_called_once()
