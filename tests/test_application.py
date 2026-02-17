"""Tests for Application coordinator."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call

from core.application import Application
from core.event_bus import EventBus, Topics
from core.plugin_base import PluginEvent
from core.models import ToolTask, ToolResult
from ui.tray import ConnectionStatus


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for Application."""
    config_manager = MagicMock()
    config_manager.get.return_value = True
    config_manager.device_id = "test-device"

    device_info = MagicMock()
    device_info.device_id = "test-device"

    plugin_manager = MagicMock()
    plugin_manager.tools = {}
    plugin_manager.get_all_tray_items = MagicMock(return_value=[])
    plugin_manager.get_failed_plugins = MagicMock(return_value={})
    plugin_manager.discover_plugins = MagicMock()
    plugin_manager.initialize_all = AsyncMock()
    plugin_manager.start_triggers = AsyncMock()
    plugin_manager.shutdown_all = AsyncMock()
    plugin_manager.execute_tool = AsyncMock()
    plugin_manager.get_capabilities = MagicMock(return_value={
        "triggers": {"desktop.trigger.mock.triggered": {"params": ["test"]}},
        "tools": {"MOCK_TOOL": {"params": ["param1"]}},
    })

    server_client = MagicMock()
    server_client.send_trigger = AsyncMock()
    server_client.link_device = AsyncMock(return_value=True)
    server_client.connect = AsyncMock()
    server_client.disconnect = AsyncMock()
    server_client.close = AsyncMock()

    tray_manager = MagicMock()
    tray_manager.show = MagicMock()
    tray_manager.hide = MagicMock()
    tray_manager.set_plugin_items = MagicMock()
    tray_manager.set_connection_status = MagicMock()

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
        assert Topics.SERVER_TOOL in event_bus._sync_handlers
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

    @pytest.mark.asyncio
    async def test_handle_server_tool(self, mock_dependencies):
        """Test handling server tools."""
        mock_dependencies["plugin_manager"].execute_tool.return_value = ToolResult(success=True)
        application = Application(**mock_dependencies)

        tool = ToolTask(
            type="TEST_TOOL",
            parameters={"key": "value"}
        )

        # Publish event
        application.event_bus.publish(Topics.SERVER_TOOL, tool)

        # Allow the async task to run
        await asyncio.sleep(0)

        # Should call execute_tool
        mock_dependencies["plugin_manager"].execute_tool.assert_called_once()

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
        """Test that run links device and connects to server."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "auto_connect": True,
            "device_key": "test-api-key",
        }.get(key, default)

        application = Application(**mock_dependencies)

        # Patch initialize and asyncio.sleep to exit immediately
        with patch.object(application, "initialize", new_callable=AsyncMock), \
             patch("asyncio.sleep", side_effect=[None, Exception("Exit loop")]):
            try:
                await application.run()
            except Exception as e:
                if str(e) != "Exit loop":
                    raise

            # Should link device first, then connect
            mock_dependencies["server_client"].link_device.assert_called_once()
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
        # Create mock tool with set_tray_manager
        mock_tool = MagicMock()
        mock_tool.set_tray_manager = MagicMock()

        mock_dependencies["plugin_manager"].tools = {"notification": mock_tool}

        application = Application(**mock_dependencies)
        application._setup_notification_plugin()

        # Should call set_tray_manager
        mock_tool.set_tray_manager.assert_called_once_with(
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
        mock_window.isVisible.return_value = False
        mock_plugin.create_window.return_value = mock_window

        application = Application(**mock_dependencies)
        application._on_plugin_click(mock_plugin)

        # Should create and show window (non-modal)
        mock_plugin.create_window.assert_called_once()
        mock_window.show.assert_called_once()
        mock_window.raise_.assert_called_once()
        mock_window.activateWindow.assert_called_once()

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
            "device_key": "new-key",
            "reconnect_interval": 5000,
            "auto_connect": True
        }.get(key, default)

        application = Application(**mock_dependencies)

        with patch("core.server_client.ServerClient") as MockServerClient:
            mock_new_client = MagicMock()
            mock_new_client.link_device = AsyncMock(return_value=True)
            mock_new_client.connect = AsyncMock()
            mock_new_client.on_tool = MagicMock()
            MockServerClient.return_value = mock_new_client

            await application._reconnect_server()

            # Should close old client
            mock_dependencies["server_client"].close.assert_called_once()

            # Should create new client
            MockServerClient.assert_called_once()

            # Should link device then connect if auto_connect
            mock_new_client.link_device.assert_called_once()
            mock_new_client.connect.assert_called_once()


class TestApplicationConnectionStatus:
    """Tests for Application connection status handling."""

    def test_subscribes_to_connection_events(self, mock_dependencies):
        """Test that Application subscribes to connection event topics."""
        event_bus = mock_dependencies["event_bus"]
        application = Application(**mock_dependencies)

        # Check that handlers are registered
        assert Topics.SERVER_CONNECTED in event_bus._sync_handlers
        assert Topics.SERVER_DISCONNECTED in event_bus._sync_handlers
        assert Topics.SERVER_ERROR in event_bus._sync_handlers
        assert Topics.UI_CONNECT_REQUESTED in event_bus._sync_handlers
        assert Topics.UI_DISCONNECT_REQUESTED in event_bus._sync_handlers

    def test_handle_server_connected(self, mock_dependencies):
        """Test handling server connected event."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.SERVER_CONNECTED, None)

        # Should update tray status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.CONNECTED
        )

    def test_handle_server_disconnected(self, mock_dependencies):
        """Test handling server disconnected event."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.SERVER_DISCONNECTED, None)

        # Should update tray status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.DISCONNECTED
        )

    def test_handle_server_error(self, mock_dependencies):
        """Test handling server error event."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.SERVER_ERROR, {"reason": "max_retries"})

        # Should update tray status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.ERROR
        )

    def test_handle_connect_request(self, mock_dependencies):
        """Test handling connect request from UI."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.UI_CONNECT_REQUESTED, None)

        # Should update tray to connecting and call connect
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.CONNECTING
        )
        mock_dependencies["server_client"].connect.assert_called_once()

    def test_handle_disconnect_request(self, mock_dependencies):
        """Test handling disconnect request from UI."""
        application = Application(**mock_dependencies)

        # Publish event
        application.event_bus.publish(Topics.UI_DISCONNECT_REQUESTED, None)

        # Should call disconnect
        mock_dependencies["server_client"].disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_sets_disconnected_status(self, mock_dependencies):
        """Test initialize sets initial disconnected status."""
        application = Application(**mock_dependencies)

        await application.initialize()

        # Should set initial status (called during initialize)
        calls = mock_dependencies["tray_manager"].set_connection_status.call_args_list
        # First call should be DISCONNECTED
        assert any(call.args[0] == ConnectionStatus.DISCONNECTED for call in calls)

    @pytest.mark.asyncio
    async def test_run_sets_connecting_status(self, mock_dependencies):
        """Test run sets connecting status before connecting."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "auto_connect": True,
            "device_key": "test-api-key",
        }.get(key, default)

        application = Application(**mock_dependencies)

        # Patch initialize and asyncio.sleep to exit immediately
        with patch.object(application, "initialize", new_callable=AsyncMock), \
             patch("asyncio.sleep", side_effect=[None, Exception("Exit loop")]):
            try:
                await application.run()
            except Exception as e:
                if str(e) != "Exit loop":
                    raise

            # Should set connecting status
            calls = mock_dependencies["tray_manager"].set_connection_status.call_args_list
            assert any(call.args[0] == ConnectionStatus.CONNECTING for call in calls)


class TestConnectWithLinking:
    """Tests for _connect_with_linking flow."""

    @pytest.mark.asyncio
    async def test_connect_with_linking_full_flow(self, mock_dependencies):
        """Test full flow: link device then connect to Centrifugo."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "device_key": "test-api-key",
        }.get(key, default)
        mock_dependencies["server_client"].link_device = AsyncMock(return_value=True)

        application = Application(**mock_dependencies)
        await application._connect_with_linking()

        # Should link device first with capabilities
        mock_dependencies["server_client"].link_device.assert_called_once_with(
            device_os=mock_dependencies["device_info"].get_platform(),
            device_name=mock_dependencies["device_info"].get_hostname(),
            capabilities=mock_dependencies["plugin_manager"].get_capabilities(),
        )
        # Should save device_linked status
        mock_dependencies["config_manager"].set.assert_called_with("device_linked", True)
        mock_dependencies["config_manager"].save.assert_called_once()
        # Should connect to Centrifugo
        mock_dependencies["server_client"].connect.assert_called_once()
        # Should set CONNECTING status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.CONNECTING
        )

    @pytest.mark.asyncio
    async def test_connect_with_linking_no_device_key(self, mock_dependencies):
        """Test that connection is skipped when no device key is set."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "device_key": "",
        }.get(key, default)

        application = Application(**mock_dependencies)
        await application._connect_with_linking()

        # Should NOT attempt to link or connect
        mock_dependencies["server_client"].link_device.assert_not_called()
        mock_dependencies["server_client"].connect.assert_not_called()
        # Should set DISCONNECTED status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.DISCONNECTED
        )

    @pytest.mark.asyncio
    async def test_connect_with_linking_no_device_key_default(self, mock_dependencies):
        """Test that connection is skipped when device key is not configured at all."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
        }.get(key, default)

        application = Application(**mock_dependencies)
        await application._connect_with_linking()

        # Should NOT attempt to link or connect
        mock_dependencies["server_client"].link_device.assert_not_called()
        mock_dependencies["server_client"].connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_with_linking_link_fails(self, mock_dependencies):
        """Test that Centrifugo connection is skipped when linking fails."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "device_key": "test-api-key",
        }.get(key, default)
        mock_dependencies["server_client"].link_device = AsyncMock(return_value=False)

        application = Application(**mock_dependencies)
        await application._connect_with_linking()

        # Should attempt to link with capabilities
        mock_dependencies["server_client"].link_device.assert_called_once_with(
            device_os=mock_dependencies["device_info"].get_platform(),
            device_name=mock_dependencies["device_info"].get_hostname(),
            capabilities=mock_dependencies["plugin_manager"].get_capabilities(),
        )
        # Should NOT connect to Centrifugo
        mock_dependencies["server_client"].connect.assert_not_called()
        # Should set ERROR status
        mock_dependencies["tray_manager"].set_connection_status.assert_called_with(
            ConnectionStatus.ERROR
        )

    @pytest.mark.asyncio
    async def test_connect_with_linking_without_plugin_manager(self, mock_dependencies):
        """Test that capabilities is None when plugin_manager is None."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "device_key": "test-api-key",
        }.get(key, default)
        mock_dependencies["plugin_manager"] = None
        mock_dependencies["server_client"].link_device = AsyncMock(return_value=True)

        application = Application(**mock_dependencies)
        await application._connect_with_linking()

        # Should link device with capabilities=None
        mock_dependencies["server_client"].link_device.assert_called_once_with(
            device_os=mock_dependencies["device_info"].get_platform(),
            device_name=mock_dependencies["device_info"].get_hostname(),
            capabilities=None,
        )

    @pytest.mark.asyncio
    async def test_connect_with_linking_sets_connecting_before_link(self, mock_dependencies):
        """Test that CONNECTING status is set before attempting to link."""
        mock_dependencies["config_manager"].get.side_effect = lambda key, default=None: {
            "device_key": "test-api-key",
        }.get(key, default)
        mock_dependencies["server_client"].link_device = AsyncMock(return_value=True)

        application = Application(**mock_dependencies)

        status_calls = []
        original_set = mock_dependencies["tray_manager"].set_connection_status
        def track_status(status):
            status_calls.append(status)
            return original_set(status)
        mock_dependencies["tray_manager"].set_connection_status = track_status

        await application._connect_with_linking()

        # First status should be CONNECTING
        assert status_calls[0] == ConnectionStatus.CONNECTING
