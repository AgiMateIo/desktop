"""Tests for core.server_client module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aioresponses import aioresponses

from core.server_client import (
    ClientHandler,
    ActionSubscriptionHandler,
    ServerClient,
)
from core.models import TriggerPayload, ActionTask


class TestClientHandler:
    """Test cases for ClientHandler class."""

    @pytest.mark.asyncio
    async def test_on_connected_calls_callback(self):
        """Test on_connected() calls the callback."""
        connected_called = False

        def on_connected():
            nonlocal connected_called
            connected_called = True

        handler = ClientHandler(
            on_connected=on_connected,
            on_disconnected=lambda: None
        )

        # Mock connected context
        ctx = Mock()
        ctx.client = "test-client-id"

        await handler.on_connected(ctx)

        assert connected_called is True

    @pytest.mark.asyncio
    async def test_on_disconnected_calls_callback(self):
        """Test on_disconnected() calls the callback."""
        disconnected_called = False

        def on_disconnected():
            nonlocal disconnected_called
            disconnected_called = True

        handler = ClientHandler(
            on_connected=lambda: None,
            on_disconnected=on_disconnected
        )

        # Mock disconnected context
        ctx = Mock()
        ctx.code = 1000
        ctx.reason = "Normal closure"

        await handler.on_disconnected(ctx)

        assert disconnected_called is True

    @pytest.mark.asyncio
    async def test_on_error_logs_error(self):
        """Test on_error() logs the error."""
        handler = ClientHandler(
            on_connected=lambda: None,
            on_disconnected=lambda: None
        )

        # Mock error context
        ctx = Mock()
        ctx.error = "Test error"

        # Should not raise exception
        await handler.on_error(ctx)


class TestActionSubscriptionHandler:
    """Test cases for ActionSubscriptionHandler class."""

    @pytest.mark.asyncio
    async def test_on_subscribed_logs_channel(self):
        """Test on_subscribed() logs channel name."""
        handler = ActionSubscriptionHandler(callback=lambda action: None)

        # Mock subscribed context
        ctx = Mock()
        ctx.channel = "test:channel"

        # Should not raise exception
        await handler.on_subscribed(ctx)

    @pytest.mark.asyncio
    async def test_on_publication_calls_callback(self):
        """Test on_publication() processes action and calls callback."""
        actions_received = []

        def callback(action):
            actions_received.append(action)

        handler = ActionSubscriptionHandler(callback=callback)

        # Mock publication context
        ctx = Mock()
        ctx.pub = Mock()
        ctx.pub.data = {
            "type": "TEST_ACTION",
            "parameters": {"key": "value"}
        }

        await handler.on_publication(ctx)

        # Give async task time to complete
        await asyncio.sleep(0.1)

        assert len(actions_received) == 1
        assert actions_received[0].type == "TEST_ACTION"
        assert actions_received[0].parameters == {"key": "value"}

    @pytest.mark.asyncio
    async def test_on_publication_handles_invalid_data(self):
        """Test on_publication() handles invalid action data."""
        callback = Mock()
        handler = ActionSubscriptionHandler(callback=callback)

        # Mock publication context with invalid data
        ctx = Mock()
        ctx.pub = Mock()
        ctx.pub.data = "invalid data"

        # Should not raise exception
        await handler.on_publication(ctx)

        # Give async task time to complete
        await asyncio.sleep(0.1)

        # Callback should not be called due to error
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_error_logs_error(self):
        """Test on_error() logs subscription errors."""
        handler = ActionSubscriptionHandler(callback=lambda action: None)

        # Mock error context
        ctx = Mock()
        ctx.error = "Subscription error"

        # Should not raise exception
        await handler.on_error(ctx)


class TestServerClientInit:
    """Test cases for ServerClient initialization."""

    def test_init(self):
        """Test ServerClient initialization."""
        client = ServerClient(
            server_url="http://test-server:8080",
            api_key="test-key",
            device_id="test-device-123",
            reconnect_interval=5000
        )

        assert client.server_url == "http://test-server:8080"
        assert client._api_key == "test-key"
        assert client._device_id == "test-device-123"
        assert client._reconnect_interval == 5.0  # Converted to seconds
        assert client.connected is False
        assert client._action_handlers == []

    def test_init_strips_trailing_slash(self):
        """Test ServerClient strips trailing slash from URL."""
        client = ServerClient(
            server_url="http://test-server:8080/",
            api_key="test-key",
            device_id="test-device"
        )

        assert client.server_url == "http://test-server:8080"


class TestServerClientProperties:
    """Test cases for ServerClient properties."""

    def test_connected_property_false(self):
        """Test connected property returns False initially."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        assert client.connected is False

    def test_connected_property_true(self):
        """Test connected property returns True when connected."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        client._connected = True
        assert client.connected is True

    def test_server_url_property(self):
        """Test server_url property."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="key",
            device_id="device"
        )

        assert client.server_url == "http://test-server"


class TestActionHandling:
    """Test cases for action handler registration and dispatch."""

    def test_on_action_registration(self):
        """Test on_action() registers handler."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        def handler(action):
            pass

        client.on_action(handler)

        assert handler in client._action_handlers
        assert len(client._action_handlers) == 1

    def test_on_action_multiple_handlers(self):
        """Test on_action() registers multiple handlers."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        handler1 = lambda action: None
        handler2 = lambda action: None

        client.on_action(handler1)
        client.on_action(handler2)

        assert len(client._action_handlers) == 2

    def test_dispatch_action_calls_handlers(self):
        """Test _dispatch_action() calls all handlers."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        actions_received = []

        def handler(action):
            actions_received.append(action)

        client.on_action(handler)

        action = ActionTask(type="TEST", parameters={})
        client._dispatch_action(action)

        assert len(actions_received) == 1
        assert actions_received[0].type == "TEST"

    def test_dispatch_action_handles_handler_error(self):
        """Test _dispatch_action() handles handler errors."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        actions_received = []

        def bad_handler(action):
            raise ValueError("Handler error")

        def good_handler(action):
            actions_received.append(action)

        client.on_action(bad_handler)
        client.on_action(good_handler)

        action = ActionTask(type="TEST", parameters={})
        client._dispatch_action(action)  # Should not crash

        # Good handler should still receive action
        assert len(actions_received) == 1


class TestHTTPTriggers:
    """Test cases for HTTP trigger sending."""

    @pytest.mark.asyncio
    async def test_send_trigger_success(self, sample_trigger_payload):
        """Test send_trigger() sends successfully."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/mobile-api/device/trigger/new",
                    status=200,
                    payload={"success": True}
                )

                result = await client.send_trigger(sample_trigger_payload)

                assert result is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_http_error(self, sample_trigger_payload):
        """Test send_trigger() handles HTTP errors."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/mobile-api/device/trigger/new",
                    status=500,
                    body="Server error"
                )

                result = await client.send_trigger(sample_trigger_payload)

                assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_404_error(self, sample_trigger_payload):
        """Test send_trigger() handles 404 errors."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/mobile-api/device/trigger/new",
                    status=404,
                    body="Not found"
                )

                result = await client.send_trigger(sample_trigger_payload)

                assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_missing_server_url(self, sample_trigger_payload):
        """Test send_trigger() handles missing server URL."""
        client = ServerClient(
            server_url="",
            api_key="test-key",
            device_id="test-device"
        )

        try:
            result = await client.send_trigger(sample_trigger_payload)

            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_missing_api_key(self, sample_trigger_payload):
        """Test send_trigger() handles missing API key."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="",
            device_id="test-device"
        )

        try:
            result = await client.send_trigger(sample_trigger_payload)

            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_network_error(self, sample_trigger_payload):
        """Test send_trigger() handles network errors."""
        client = ServerClient(
            server_url="http://test-server",
            api_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/mobile-api/device/trigger/new",
                    exception=aiohttp.ClientError("Network error")
                )

                result = await client.send_trigger(sample_trigger_payload)

                assert result is False
        finally:
            await client.close()


class TestWebSocketConnection:
    """Test cases for WebSocket connection."""

    def test_get_ws_url_http(self):
        """Test _get_ws_url() converts http to ws."""
        client = ServerClient(
            server_url="http://test-server:8080",
            api_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        assert ws_url == "ws://test-server:8080/connection/websocket"

    def test_get_ws_url_https(self):
        """Test _get_ws_url() converts https to wss."""
        client = ServerClient(
            server_url="https://test-server:443",
            api_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        assert ws_url == "wss://test-server:443/connection/websocket"

    @pytest.mark.asyncio
    async def test_get_token(self):
        """Test _get_token() returns API key."""
        client = ServerClient(
            server_url="http://test",
            api_key="test-api-key",
            device_id="device"
        )

        token = await client._get_token()

        assert token == "test-api-key"

    @pytest.mark.asyncio
    async def test_connect_missing_config(self):
        """Test connect() with missing configuration."""
        client = ServerClient(
            server_url="",
            api_key="",
            device_id="device"
        )

        result = await client.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test disconnect() cleans up resources."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Mock WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.disconnect = AsyncMock()
        client._ws_client = mock_ws_client

        # Mock subscription
        mock_subscription = Mock()
        mock_subscription.unsubscribe = AsyncMock()
        client._subscription = mock_subscription

        client._connected = True

        await client.disconnect()

        # Verify cleanup
        assert client._connected is False
        assert client._ws_client is None
        assert client._subscription is None
        mock_ws_client.disconnect.assert_called_once()
        mock_subscription.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_handles_errors(self):
        """Test disconnect() handles errors gracefully."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Mock WebSocket client that raises error
        client._ws_client = Mock()
        client._ws_client.disconnect = AsyncMock(side_effect=Exception("Disconnect error"))

        # Should not raise exception
        await client.disconnect()

        assert client._ws_client is None
        assert client._connected is False


class TestReconnection:
    """Test cases for reconnection logic."""

    def test_on_ws_connected_sets_flag(self):
        """Test _on_ws_connected() sets connected flag."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        assert client.connected is False

        client._on_ws_connected()

        assert client.connected is True

    @pytest.mark.asyncio
    async def test_on_ws_disconnected_clears_flag(self):
        """Test _on_ws_disconnected() clears connected flag."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        client._connected = True
        client._should_reconnect = True

        client._on_ws_disconnected()

        assert client.connected is False

        # Cleanup reconnect task if created
        if client._reconnect_task:
            client._reconnect_task.cancel()
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_schedule_reconnect_creates_task(self):
        """Test _schedule_reconnect() creates reconnect task."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        client._should_reconnect = True
        client._schedule_reconnect()

        assert client._reconnect_task is not None
        assert isinstance(client._reconnect_task, asyncio.Task)
        assert not client._reconnect_task.done()

        # Cleanup - cancel and wait briefly to avoid warnings
        client._reconnect_task.cancel()
        await asyncio.sleep(0.01)

    def test_schedule_reconnect_skips_if_disabled(self):
        """Test _schedule_reconnect() skips if reconnect disabled."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        client._should_reconnect = False
        client._schedule_reconnect()

        assert client._reconnect_task is None

    @pytest.mark.asyncio
    async def test_schedule_reconnect_skips_if_task_running(self):
        """Test _schedule_reconnect() doesn't create duplicate tasks."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        client._should_reconnect = True
        client._schedule_reconnect()

        first_task = client._reconnect_task

        # Try to schedule again
        client._schedule_reconnect()

        # Should be same task
        assert client._reconnect_task is first_task

        # Cleanup - cancel and wait briefly to avoid warnings
        client._reconnect_task.cancel()
        await asyncio.sleep(0.01)


class TestCleanup:
    """Test cases for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_disconnects_websocket(self):
        """Test close() disconnects WebSocket."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Mock WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.disconnect = AsyncMock()
        client._ws_client = mock_ws_client

        await client.close()

        mock_ws_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_closes_http_session(self):
        """Test close() closes HTTP session."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Mock HTTP session
        mock_http_session = Mock()
        mock_http_session.closed = False
        mock_http_session.close = AsyncMock()
        client._http_session = mock_http_session

        await client.close()

        mock_http_session.close.assert_called_once()
        assert client._http_session is None

    @pytest.mark.asyncio
    async def test_close_handles_missing_resources(self):
        """Test close() handles missing resources gracefully."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Should not raise exception
        await client.close()


# Import asyncio for async tests
import asyncio
import aiohttp

from core.event_bus import EventBus, Topics


class TestServerClientEventBus:
    """Test cases for ServerClient EventBus integration."""

    def test_init_with_event_bus(self):
        """Test ServerClient initialization with EventBus."""
        event_bus = EventBus()
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device",
            event_bus=event_bus
        )

        assert client._event_bus is event_bus

    def test_on_ws_connected_publishes_event(self):
        """Test _on_ws_connected() publishes SERVER_CONNECTED event."""
        event_bus = EventBus()
        events_received = []
        event_bus.subscribe(Topics.SERVER_CONNECTED, lambda data: events_received.append(data))

        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device",
            event_bus=event_bus
        )

        client._on_ws_connected()

        assert len(events_received) == 1
        assert events_received[0] is None
        assert client._connected is True

    def test_on_ws_disconnected_publishes_event(self):
        """Test _on_ws_disconnected() publishes SERVER_DISCONNECTED event."""
        event_bus = EventBus()
        events_received = []
        event_bus.subscribe(Topics.SERVER_DISCONNECTED, lambda data: events_received.append(data))

        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device",
            event_bus=event_bus
        )
        client._connected = True
        client._should_reconnect = False  # Prevent reconnect task

        client._on_ws_disconnected()

        assert len(events_received) == 1
        assert events_received[0] is None
        assert client._connected is False

    def test_max_reconnect_publishes_error_event(self):
        """Test max reconnect attempts publishes SERVER_ERROR event."""
        event_bus = EventBus()
        events_received = []
        event_bus.subscribe(Topics.SERVER_ERROR, lambda data: events_received.append(data))

        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device",
            max_reconnect_attempts=3,
            event_bus=event_bus
        )
        client._should_reconnect = True
        client._reconnect_attempts = 3  # Already at max

        client._schedule_reconnect()

        assert len(events_received) == 1
        assert events_received[0] == {"reason": "max_retries"}
        assert client._should_reconnect is False

    def test_dispatch_action_to_event_bus(self):
        """Test _dispatch_action() publishes to EventBus."""
        event_bus = EventBus()
        actions_received = []
        event_bus.subscribe(Topics.SERVER_ACTION, lambda data: actions_received.append(data))

        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device",
            event_bus=event_bus
        )

        action = ActionTask(type="TEST", parameters={"key": "value"})
        client._dispatch_action(action)

        assert len(actions_received) == 1
        assert actions_received[0].type == "TEST"

    def test_on_ws_connected_without_event_bus(self):
        """Test _on_ws_connected() works without EventBus."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )

        # Should not raise
        client._on_ws_connected()
        assert client._connected is True

    def test_on_ws_disconnected_without_event_bus(self):
        """Test _on_ws_disconnected() works without EventBus."""
        client = ServerClient(
            server_url="http://test",
            api_key="key",
            device_id="device"
        )
        client._connected = True
        client._should_reconnect = False

        # Should not raise
        client._on_ws_disconnected()
        assert client._connected is False
