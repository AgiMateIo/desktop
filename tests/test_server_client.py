"""Tests for core.server_client module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aioresponses import aioresponses

from core.server_client import (
    ClientHandler,
    ToolSubscriptionHandler,
    ServerClient,
)
from core.models import TriggerPayload, ToolTask


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


class TestToolSubscriptionHandler:
    """Test cases for ToolSubscriptionHandler class."""

    @pytest.mark.asyncio
    async def test_on_subscribed_logs_channel(self):
        """Test on_subscribed() logs channel name."""
        handler = ToolSubscriptionHandler(callback=lambda tool: None)

        # Mock subscribed context
        ctx = Mock()
        ctx.channel = "test:channel"

        # Should not raise exception
        await handler.on_subscribed(ctx)

    @pytest.mark.asyncio
    async def test_on_publication_calls_callback(self):
        """Test on_publication() processes tool and calls callback."""
        tools_received = []

        def callback(tool):
            tools_received.append(tool)

        handler = ToolSubscriptionHandler(callback=callback)

        # Mock publication context
        ctx = Mock()
        ctx.pub = Mock()
        ctx.pub.data = {
            "type": "TEST_TOOL",
            "parameters": {"key": "value"}
        }

        await handler.on_publication(ctx)

        # Give async task time to complete
        await asyncio.sleep(0.1)

        assert len(tools_received) == 1
        assert tools_received[0].type == "TEST_TOOL"
        assert tools_received[0].parameters == {"key": "value"}

    @pytest.mark.asyncio
    async def test_on_publication_handles_invalid_data(self):
        """Test on_publication() handles invalid tool data."""
        callback = Mock()
        handler = ToolSubscriptionHandler(callback=callback)

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
        handler = ToolSubscriptionHandler(callback=lambda tool: None)

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
            device_key="test-key",
            device_id="test-device-123",
            reconnect_interval=5000
        )

        assert client.server_url == "http://test-server:8080"
        assert client._device_key == "test-key"
        assert client._device_id == "test-device-123"
        assert client._reconnect_interval == 5.0  # Converted to seconds
        assert client.connected is False
        assert client._tool_handlers == []

    def test_init_strips_trailing_slash(self):
        """Test ServerClient strips trailing slash from URL."""
        client = ServerClient(
            server_url="http://test-server:8080/",
            device_key="test-key",
            device_id="test-device"
        )

        assert client.server_url == "http://test-server:8080"


class TestServerClientProperties:
    """Test cases for ServerClient properties."""

    def test_connected_property_false(self):
        """Test connected property returns False initially."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        assert client.connected is False

    def test_connected_property_true(self):
        """Test connected property returns True when connected."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        client._connected = True
        assert client.connected is True

    def test_server_url_property(self):
        """Test server_url property."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="key",
            device_id="device"
        )

        assert client.server_url == "http://test-server"


class TestToolHandling:
    """Test cases for tool handler registration and dispatch."""

    def test_on_tool_registration(self):
        """Test on_tool() registers handler."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        def handler(tool):
            pass

        client.on_tool(handler)

        assert handler in client._tool_handlers
        assert len(client._tool_handlers) == 1

    def test_on_tool_multiple_handlers(self):
        """Test on_tool() registers multiple handlers."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        handler1 = lambda tool: None
        handler2 = lambda tool: None

        client.on_tool(handler1)
        client.on_tool(handler2)

        assert len(client._tool_handlers) == 2

    def test_dispatch_tool_calls_handlers(self):
        """Test _dispatch_tool() calls all handlers."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        tools_received = []

        def handler(tool):
            tools_received.append(tool)

        client.on_tool(handler)

        tool = ToolTask(type="TEST", parameters={})
        client._dispatch_tool(tool)

        assert len(tools_received) == 1
        assert tools_received[0].type == "TEST"

    def test_dispatch_tool_handles_handler_error(self):
        """Test _dispatch_tool() handles handler errors."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        tools_received = []

        def bad_handler(tool):
            raise ValueError("Handler error")

        def good_handler(tool):
            tools_received.append(tool)

        client.on_tool(bad_handler)
        client.on_tool(good_handler)

        tool = ToolTask(type="TEST", parameters={})
        client._dispatch_tool(tool)  # Should not crash

        # Good handler should still receive tool
        assert len(tools_received) == 1


class TestHTTPTriggers:
    """Test cases for HTTP trigger sending."""

    @pytest.mark.asyncio
    async def test_send_trigger_success(self, sample_trigger_payload):
        """Test send_trigger() sends successfully."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/trigger/new",
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
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/trigger/new",
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
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/trigger/new",
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
            device_key="test-key",
            device_id="test-device"
        )

        try:
            result = await client.send_trigger(sample_trigger_payload)

            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_send_trigger_missing_device_key(self, sample_trigger_payload):
        """Test send_trigger() handles missing device key."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="",
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
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/trigger/new",
                    exception=aiohttp.ClientError("Network error")
                )

                result = await client.send_trigger(sample_trigger_payload)

                assert result is False
        finally:
            await client.close()


class TestWebSocketConnection:
    """Test cases for WebSocket connection."""

    def test_get_ws_url_http_multi_level_domain(self):
        """Test _get_ws_url() always uses wss:// for multi-level domains."""
        client = ServerClient(
            server_url="http://api.example.com",
            device_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        # Even though server_url is http://, wss:// is used for production domains
        assert ws_url == "wss://centrifugo.example.com/connection/websocket"

    def test_get_ws_url_https(self):
        """Test _get_ws_url() converts https to wss with centrifugo subdomain."""
        client = ServerClient(
            server_url="https://api.agimate.io",
            device_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        assert ws_url == "wss://centrifugo.agimate.io/connection/websocket"

    def test_get_ws_url_localhost_http(self):
        """Test _get_ws_url() uses ws:// for localhost with http."""
        client = ServerClient(
            server_url="http://localhost:8080",
            device_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        assert ws_url == "ws://localhost:8080/connection/websocket"

    def test_get_ws_url_localhost_https(self):
        """Test _get_ws_url() uses wss:// for localhost with https."""
        client = ServerClient(
            server_url="https://localhost:8080",
            device_key="key",
            device_id="device"
        )

        ws_url = client._get_ws_url()

        assert ws_url == "wss://localhost:8080/connection/websocket"

    def test_get_ws_url_server_provided(self):
        """Test _get_ws_url() uses server-provided wsUrl when available."""
        client = ServerClient(
            server_url="https://api.agimate.io",
            device_key="key",
            device_id="device"
        )
        client._ws_url = "wss://custom-centrifugo.agimate.io/connection/websocket"

        ws_url = client._get_ws_url()

        assert ws_url == "wss://custom-centrifugo.agimate.io/connection/websocket"

    @pytest.mark.asyncio
    async def test_get_connection_token_returns_cached_token(self):
        """Test _get_connection_token() returns cached token."""
        client = ServerClient(
            server_url="http://test",
            device_key="test-api-key",
            device_id="device"
        )
        client._connection_token = "cached-connection-token"

        token = await client._get_connection_token()

        assert token == "cached-connection-token"

    @pytest.mark.asyncio
    async def test_get_subscription_token_returns_cached_token(self):
        """Test _get_subscription_token() returns cached token."""
        client = ServerClient(
            server_url="http://test",
            device_key="test-api-key",
            device_id="device"
        )
        client._subscription_token = "cached-subscription-token"

        token = await client._get_subscription_token("channel")

        assert token == "cached-subscription-token"

    @pytest.mark.asyncio
    async def test_fetch_centrifugo_tokens_extracts_ws_url(self):
        """Test _fetch_centrifugo_tokens() extracts wsUrl from response."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/centrifugo/token",
                    status=200,
                    payload={
                        "response": {
                            "connectionToken": "conn-token",
                            "subscriptionToken": "sub-token",
                            "channel": "device:test",
                            "wsUrl": "wss://centrifugo.agimate.io/connection/websocket"
                        }
                    }
                )

                result = await client._fetch_centrifugo_tokens()

                assert result is True
                assert client._ws_url == "wss://centrifugo.agimate.io/connection/websocket"
                assert client._connection_token == "conn-token"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_fetch_centrifugo_tokens_without_ws_url(self):
        """Test _fetch_centrifugo_tokens() works when wsUrl is not in response."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/centrifugo/token",
                    status=200,
                    payload={
                        "response": {
                            "connectionToken": "conn-token",
                            "subscriptionToken": "sub-token",
                            "channel": "device:test"
                        }
                    }
                )

                result = await client._fetch_centrifugo_tokens()

                assert result is True
                assert client._ws_url is None
                assert client._connection_token == "conn-token"
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_connect_missing_config(self):
        """Test connect() with missing configuration."""
        client = ServerClient(
            server_url="",
            device_key="",
            device_id="device"
        )

        result = await client.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self):
        """Test disconnect() cleans up resources."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
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

        client._ws_url = "wss://centrifugo.example.com/connection/websocket"

        await client.disconnect()

        # Verify cleanup
        assert client._connected is False
        assert client._ws_client is None
        assert client._subscription is None
        assert client._ws_url is None
        mock_ws_client.disconnect.assert_called_once()
        mock_subscription.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_handles_errors(self):
        """Test disconnect() handles errors gracefully."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
            device_id="device"
        )

        # Should not raise exception
        await client.close()


class TestLinkDevice:
    """Test cases for device linking."""

    @pytest.mark.asyncio
    async def test_link_device_success(self):
        """Test link_device() succeeds with 200 response."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=200,
                    payload={"success": True}
                )

                result = await client.link_device("macos", "my-mac")

                assert result is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_server_error(self):
        """Test link_device() returns False on server error."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=500,
                    body="Internal Server Error"
                )

                result = await client.link_device("macos", "my-mac")

                assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_auth_error(self):
        """Test link_device() returns False on 401 unauthorized."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="bad-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=401,
                    body="Unauthorized"
                )

                result = await client.link_device("macos", "my-mac")

                assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_network_error(self):
        """Test link_device() returns False on network error."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    exception=aiohttp.ClientError("Connection refused")
                )

                result = await client.link_device("macos", "my-mac")

                assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_missing_server_url(self):
        """Test link_device() returns False without server URL."""
        client = ServerClient(
            server_url="",
            device_key="test-key",
            device_id="test-device"
        )

        try:
            result = await client.link_device("macos", "my-mac")
            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_missing_device_key(self):
        """Test link_device() returns False without device key."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="",
            device_id="test-device"
        )

        try:
            result = await client.link_device("macos", "my-mac")
            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_sends_correct_payload(self):
        """Test link_device() sends correct device info in payload."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="device-123"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=200,
                    payload={"success": True}
                )

                result = await client.link_device("linux", "my-server")

                assert result is True
                # Verify a request was made to the link endpoint
                assert len(m.requests) == 1
                request_url = list(m.requests.keys())[0]
                assert str(request_url[1]) == "http://test-server/device/registration/link"
        finally:
            await client.close()


class TestLinkDeviceCapabilities:
    """Test cases for device linking with capabilities."""

    @pytest.mark.asyncio
    async def test_link_device_with_capabilities(self):
        """Test link_device() includes capabilities in payload."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="device-123"
        )

        capabilities = {
            "triggers": {
                "desktop.trigger.filewatcher.created": {"params": ["path", "filename"]},
            },
            "tools": {
                "desktop.tool.notification.show": {"params": ["title", "message"]},
            },
        }

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=200,
                    payload={"success": True}
                )

                result = await client.link_device("macos", "my-mac", capabilities=capabilities)

                assert result is True
                # Verify request was made
                assert len(m.requests) == 1
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_without_capabilities(self):
        """Test link_device() works without capabilities (backward compatible)."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="device-123"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=200,
                    payload={"success": True}
                )

                result = await client.link_device("macos", "my-mac")

                assert result is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_link_device_with_none_capabilities(self):
        """Test link_device() with None capabilities doesn't add extra fields."""
        client = ServerClient(
            server_url="http://test-server",
            device_key="test-key",
            device_id="device-123"
        )

        try:
            with aioresponses() as m:
                m.post(
                    "http://test-server/device/registration/link",
                    status=200,
                    payload={"success": True}
                )

                result = await client.link_device("macos", "my-mac", capabilities=None)

                assert result is True
        finally:
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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
            device_key="key",
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

    def test_dispatch_tool_to_event_bus(self):
        """Test _dispatch_tool() publishes to EventBus."""
        event_bus = EventBus()
        tools_received = []
        event_bus.subscribe(Topics.SERVER_TOOL, lambda data: tools_received.append(data))

        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device",
            event_bus=event_bus
        )

        tool = ToolTask(type="TEST", parameters={"key": "value"})
        client._dispatch_tool(tool)

        assert len(tools_received) == 1
        assert tools_received[0].type == "TEST"

    def test_on_ws_connected_without_event_bus(self):
        """Test _on_ws_connected() works without EventBus."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )

        # Should not raise
        client._on_ws_connected()
        assert client._connected is True

    def test_on_ws_disconnected_without_event_bus(self):
        """Test _on_ws_disconnected() works without EventBus."""
        client = ServerClient(
            server_url="http://test",
            device_key="key",
            device_id="device"
        )
        client._connected = True
        client._should_reconnect = False

        # Should not raise
        client._on_ws_disconnected()
        assert client._connected is False
