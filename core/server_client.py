"""Server client for HTTP triggers and WebSocket tools."""

import asyncio
import logging
from typing import Any, Callable, TYPE_CHECKING
from urllib.parse import urlparse

import aiohttp
from centrifuge import (
    Client,
    ClientEventHandler,
    SubscriptionEventHandler,
    ConnectedContext,
    DisconnectedContext,
    ErrorContext,
    SubscribedContext,
    PublicationContext,
)

from .models import TriggerPayload, ToolTask
from .api_endpoints import (
    ENDPOINT_DEVICE_LINK,
    ENDPOINT_DEVICE_TRIGGER,
    ENDPOINT_CENTRIFUGO_TOKEN,
    ENDPOINT_WEBSOCKET,
    HEADER_CONTENT_TYPE,
    HEADER_DEVICE_AUTH,
    CONTENT_TYPE_JSON,
)
from .constants import (
    DEFAULT_RECONNECT_INTERVAL_MS,
    DEFAULT_HTTP_TIMEOUT_MS,
    DEFAULT_MAX_RECONNECT_ATTEMPTS,
)
from .retry import retry_async, RetryConfig

if TYPE_CHECKING:
    from .event_bus import EventBus, Topics

logger = logging.getLogger(__name__)


class ClientHandler(ClientEventHandler):
    """Handler for Centrifugo client events."""

    def __init__(self, on_connected: Callable[[], None], on_disconnected: Callable[[], None]):
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

    async def on_connected(self, ctx: ConnectedContext) -> None:
        logger.info(f"Centrifugo connected: client_id={ctx.client}")
        self._on_connected()

    async def on_disconnected(self, ctx: DisconnectedContext) -> None:
        logger.info(f"Centrifugo disconnected: code={ctx.code}, reason={ctx.reason}")
        self._on_disconnected()

    async def on_error(self, ctx: ErrorContext) -> None:
        logger.error(f"Centrifugo client error: {ctx.error}")


class ToolSubscriptionHandler(SubscriptionEventHandler):
    """Handler for Centrifugo subscription events."""

    def __init__(self, callback: Callable[[ToolTask], None]):
        self._callback = callback
        self._background_tasks: set[asyncio.Task] = set()

    def _create_task(self, coro) -> asyncio.Task:
        """Create a background task with automatic cleanup."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def on_subscribed(self, ctx: SubscribedContext) -> None:
        logger.info(f"Subscribed to channel: {ctx.channel}")

    async def on_publication(self, ctx: PublicationContext) -> None:
        """Handle incoming publication (tool from server)."""
        try:
            data = ctx.pub.data
            logger.info(f"Received tool: {data}")
            tool = ToolTask.from_dict(data)
            # Use background task to not block the read loop
            self._create_task(self._handle_tool(tool))
        except Exception as e:
            logger.error(f"Error processing tool: {e}")

    async def _handle_tool(self, tool: ToolTask) -> None:
        """Handle tool asynchronously."""
        try:
            self._callback(tool)
        except Exception as e:
            logger.error(f"Error in tool callback: {e}")

    async def on_error(self, ctx: ErrorContext) -> None:
        logger.error(f"Subscription error: {ctx.error}")


class ServerClient:
    """Client for server communication via HTTP and WebSocket."""

    def __init__(
        self,
        server_url: str,
        device_key: str,
        device_id: str,
        reconnect_interval: int = DEFAULT_RECONNECT_INTERVAL_MS,
        max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS,
        http_timeout: float = DEFAULT_HTTP_TIMEOUT_MS / 1000,
        event_bus: "EventBus | None" = None
    ):
        """Initialize server client.

        Args:
            server_url: Server base URL
            device_key: Device key for authentication
            device_id: Device ID
            reconnect_interval: WebSocket reconnection interval in milliseconds
            max_reconnect_attempts: Maximum number of reconnection attempts
            http_timeout: HTTP timeout in seconds
            event_bus: Optional EventBus for decoupled communication.
                      If provided, tools will be published to the bus.
                      If None, old callback mechanism is used.
        """
        self._server_url = server_url.rstrip("/")
        self._device_key = device_key
        self._device_id = device_id
        self._reconnect_interval = reconnect_interval / 1000  # Convert to seconds
        self._max_reconnect_attempts = max_reconnect_attempts
        self._http_timeout = http_timeout
        self._event_bus = event_bus

        self._http_session: aiohttp.ClientSession | None = None
        self._ws_client: Client | None = None
        self._subscription = None
        self._connected = False
        self._tool_handlers: list[Callable[[ToolTask], None]] = []
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect = False
        self._reconnect_attempts = 0

        # Centrifugo
        self._ws_url: str | None = None
        self._connection_token: str | None = None
        self._subscription_token: str | None = None
        self._channel: str | None = None

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected

    @property
    def server_url(self) -> str:
        """Get the server URL."""
        return self._server_url

    def on_tool(self, handler: Callable[[ToolTask], None]) -> None:
        """Register a handler for incoming tools.

        Note: Only used when EventBus is not provided (backward compatibility).
        """
        self._tool_handlers.append(handler)

    def _dispatch_tool(self, tool: ToolTask) -> None:
        """Dispatch a tool to EventBus or registered handlers.

        If EventBus is available, publishes to SERVER_TOOL topic.
        Otherwise, calls registered callback handlers (backward compatibility).
        """
        # New approach: publish to EventBus
        if self._event_bus:
            from .event_bus import Topics
            self._event_bus.publish(Topics.SERVER_TOOL, tool)
            return

        # Old approach: call handlers directly (backward compatibility)
        for handler in self._tool_handlers:
            try:
                handler(tool)
            except Exception as e:
                logger.error(f"Error in tool handler: {e}")

    def _on_ws_connected(self) -> None:
        """Called when WebSocket connects."""
        self._connected = True
        self._reconnect_attempts = 0  # Reset counter on successful connection
        logger.info("WebSocket connected")
        if self._event_bus:
            from .event_bus import Topics
            self._event_bus.publish(Topics.SERVER_CONNECTED, None)

    def _on_ws_disconnected(self) -> None:
        """Called when WebSocket disconnects."""
        self._connected = False
        logger.info("WebSocket disconnected")
        if self._event_bus:
            from .event_bus import Topics
            self._event_bus.publish(Topics.SERVER_DISCONNECTED, None)
        self._schedule_reconnect()

    # =====================
    # HTTP Client (Triggers)
    # =====================

    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session exists."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                headers={
                    HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
                    HEADER_DEVICE_AUTH: self._device_key
                }
            )
        return self._http_session

    @retry_async(RetryConfig(max_attempts=3, initial_delay=1.0))
    async def _send_trigger_with_retry(self, url: str, data: dict) -> aiohttp.ClientResponse:
        """Internal method that performs HTTP POST with retry logic."""
        session = await self._ensure_http_session()
        timeout = aiohttp.ClientTimeout(total=self._http_timeout)
        async with session.post(url, json=data, timeout=timeout) as response:
            # Raise for 5xx errors (will trigger retry)
            if response.status >= 500:
                response.raise_for_status()
            return response

    async def send_trigger(self, payload: TriggerPayload) -> bool:
        """
        Send a trigger event to the server with retry logic.

        Args:
            payload: The trigger payload to send.

        Returns:
            True if the trigger was sent successfully, False otherwise.
        """
        if not self._server_url or not self._device_key:
            logger.warning("Server URL or device key not configured, skipping trigger")
            return False

        url = f"{self._server_url}{ENDPOINT_DEVICE_TRIGGER}"

        try:
            response = await self._send_trigger_with_retry(url, payload.to_dict())
            if response.status == 200:
                logger.info(f"Trigger sent successfully: {payload.name}")
                return True
            else:
                body = await response.text()
                logger.error(f"Failed to send trigger: {response.status} - {body}")
                return False
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error sending trigger: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending trigger: {e}")
            return False

    # =====================
    # WebSocket Client (Tools via Centrifugo)
    # =====================

    def _get_ws_url(self) -> str:
        """Get WebSocket URL for Centrifugo connection.

        Uses server-provided wsUrl if available, otherwise derives from server_url
        by replacing the first subdomain with 'centrifugo'.
        Always uses wss:// when constructing a URL for a multi-level domain
        (production), since Centrifugo servers require TLS.
        """
        if self._ws_url:
            return self._ws_url

        # Default: replace first subdomain with "centrifugo"
        # e.g. https://api.agimate.io -> wss://centrifugo.agimate.io/connection/websocket
        parsed = urlparse(self._server_url)
        host = parsed.netloc
        parts = host.split(".", 1)
        if len(parts) == 2:
            # Multi-level domain (e.g. api.agimate.io) — always use wss://
            # because production Centrifugo servers require TLS
            host = f"centrifugo.{parts[1]}"
            ws_scheme = "wss"
        else:
            # Single-level host (e.g. localhost:8080) — respect original scheme
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        return f"{ws_scheme}://{host}{ENDPOINT_WEBSOCKET}"

    async def _fetch_centrifugo_tokens(self) -> bool:
        """Fetch connection and subscription tokens from backend.

        Returns:
            True if tokens were fetched successfully, False otherwise.
        """
        url = f"{self._server_url}{ENDPOINT_CENTRIFUGO_TOKEN}"
        logger.info("Fetching Centrifugo tokens...")

        try:
            session = await self._ensure_http_session()
            timeout = aiohttp.ClientTimeout(total=self._http_timeout)
            payload = {"deviceId": self._device_id}
            async with session.post(url, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    resp = data["response"]
                    self._connection_token = resp["connectionToken"]
                    self._subscription_token = resp["subscriptionToken"]
                    self._channel = resp["channel"]
                    self._ws_url = resp.get("wsUrl")
                    logger.info(f"Centrifugo tokens received for channel: {self._channel}")
                    return True
                else:
                    body = await response.text()
                    logger.error(f"Failed to fetch Centrifugo tokens: {response.status} - {body}")
                    return False
        except Exception as e:
            logger.error(f"Error fetching Centrifugo tokens: {e}")
            return False

    async def _get_connection_token(self) -> str:
        """Token provider for Centrifugo connection."""
        if not self._connection_token:
            await self._fetch_centrifugo_tokens()
        return self._connection_token or ""

    async def _get_subscription_token(self, channel: str) -> str:
        """Token provider for Centrifugo subscription."""
        if not self._subscription_token:
            await self._fetch_centrifugo_tokens()
        return self._subscription_token or ""

    async def link_device(self, device_os: str, device_name: str, capabilities: dict | None = None) -> bool:
        """Link device with the server.

        Args:
            device_os: Device platform (e.g., 'macos', 'windows', 'linux')
            device_name: Device hostname
            capabilities: Optional dict with 'triggers' and 'tools' capabilities

        Returns:
            True if device was linked successfully, False otherwise.
        """
        if not self._server_url or not self._device_key:
            logger.warning("Server URL or device key not configured, skipping link")
            return False

        url = f"{self._server_url}{ENDPOINT_DEVICE_LINK}"
        payload = {
            "deviceId": self._device_id,
            "deviceOs": device_os,
            "deviceName": device_name,
        }
        if capabilities:
            payload.update(capabilities)

        try:
            session = await self._ensure_http_session()
            timeout = aiohttp.ClientTimeout(total=self._http_timeout)
            async with session.post(url, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    logger.info("Device linked successfully")
                    return True
                else:
                    body = await response.text()
                    logger.error(f"Failed to link device: {response.status} - {body}")
                    return False
        except Exception as e:
            logger.error(f"Error linking device: {e}")
            return False

    async def connect(self) -> bool:
        """
        Connect to the WebSocket server and subscribe to tools channel.

        Returns:
            True if connected successfully, False otherwise.
        """
        if not self._server_url or not self._device_key:
            logger.warning("Server URL or device key not configured, skipping connection")
            return False

        self._should_reconnect = True

        try:
            # Fetch Centrifugo tokens first
            if not await self._fetch_centrifugo_tokens():
                logger.error("Failed to fetch Centrifugo tokens")
                self._schedule_reconnect()
                return False

            ws_url = self._get_ws_url()
            logger.info(f"Connecting to WebSocket: {ws_url}")

            # Create client event handler
            client_handler = ClientHandler(
                on_connected=self._on_ws_connected,
                on_disconnected=self._on_ws_disconnected
            )

            # Create Centrifugo client with token callback
            self._ws_client = Client(
                ws_url,
                events=client_handler,
                get_token=self._get_connection_token,
            )

            # Connect to server
            await self._ws_client.connect()
            logger.info("WebSocket connection initiated")

            # Subscribe to tools channel using channel from backend response
            sub_handler = ToolSubscriptionHandler(self._dispatch_tool)
            self._subscription = self._ws_client.new_subscription(
                self._channel,
                sub_handler,
                get_token=self._get_subscription_token,
            )
            await self._subscription.subscribe()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self._connected = False
            self._schedule_reconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False
        self._reconnect_attempts = 0  # Reset counter on explicit disconnect

        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._subscription:
            try:
                await self._subscription.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")
            self._subscription = None

        if self._ws_client:
            try:
                await self._ws_client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
            finally:
                self._ws_client = None
                self._connected = False
                logger.info("WebSocket disconnected")

        # Clear Centrifugo tokens and WS URL
        self._ws_url = None
        self._connection_token = None
        self._subscription_token = None
        self._channel = None

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._should_reconnect:
            return

        if self._reconnect_task and not self._reconnect_task.done():
            return

        # Check max reconnect attempts
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(
                f"Max reconnection attempts ({self._max_reconnect_attempts}) reached. "
                "Giving up."
            )
            self._should_reconnect = False
            if self._event_bus:
                from .event_bus import Topics
                self._event_bus.publish(Topics.SERVER_ERROR, {"reason": "max_retries"})
            return

        self._reconnect_attempts += 1

        # Calculate delay with exponential backoff: 5s, 10s, 20s, 40s, ...
        # Capped at 60s
        delay = min(
            self._reconnect_interval * (2 ** (self._reconnect_attempts - 1)),
            60.0
        )

        async def reconnect():
            await asyncio.sleep(delay)
            if self._should_reconnect:
                logger.info(
                    f"Attempting to reconnect... (attempt {self._reconnect_attempts}/"
                    f"{self._max_reconnect_attempts})"
                )
                await self.connect()

        self._reconnect_task = asyncio.create_task(reconnect())

    # =====================
    # Cleanup
    # =====================

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        await self.disconnect()

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

        logger.info("Server client closed")
