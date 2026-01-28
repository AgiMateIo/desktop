"""Server client for HTTP triggers and WebSocket actions."""

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

from .models import TriggerPayload, ActionTask
from .api_endpoints import (
    ENDPOINT_DEVICE_TRIGGER,
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


class ActionSubscriptionHandler(SubscriptionEventHandler):
    """Handler for Centrifugo subscription events."""

    def __init__(self, callback: Callable[[ActionTask], None]):
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
        """Handle incoming publication (action from server)."""
        try:
            data = ctx.pub.data
            logger.info(f"Received action: {data}")
            action = ActionTask.from_dict(data)
            # Use background task to not block the read loop
            self._create_task(self._handle_action(action))
        except Exception as e:
            logger.error(f"Error processing action: {e}")

    async def _handle_action(self, action: ActionTask) -> None:
        """Handle action asynchronously."""
        try:
            self._callback(action)
        except Exception as e:
            logger.error(f"Error in action callback: {e}")

    async def on_error(self, ctx: ErrorContext) -> None:
        logger.error(f"Subscription error: {ctx.error}")


class ServerClient:
    """Client for server communication via HTTP and WebSocket."""

    def __init__(
        self,
        server_url: str,
        api_key: str,
        device_id: str,
        reconnect_interval: int = DEFAULT_RECONNECT_INTERVAL_MS,
        max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS,
        http_timeout: float = DEFAULT_HTTP_TIMEOUT_MS / 1000,
        event_bus: "EventBus | None" = None
    ):
        """Initialize server client.

        Args:
            server_url: Server base URL
            api_key: API key for authentication
            device_id: Device ID
            reconnect_interval: WebSocket reconnection interval in milliseconds
            max_reconnect_attempts: Maximum number of reconnection attempts
            http_timeout: HTTP timeout in seconds
            event_bus: Optional EventBus for decoupled communication.
                      If provided, actions will be published to the bus.
                      If None, old callback mechanism is used.
        """
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._device_id = device_id
        self._reconnect_interval = reconnect_interval / 1000  # Convert to seconds
        self._max_reconnect_attempts = max_reconnect_attempts
        self._http_timeout = http_timeout
        self._event_bus = event_bus

        self._http_session: aiohttp.ClientSession | None = None
        self._ws_client: Client | None = None
        self._subscription = None
        self._connected = False
        self._action_handlers: list[Callable[[ActionTask], None]] = []
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect = False
        self._reconnect_attempts = 0

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected

    @property
    def server_url(self) -> str:
        """Get the server URL."""
        return self._server_url

    def on_action(self, handler: Callable[[ActionTask], None]) -> None:
        """Register a handler for incoming actions.

        Note: Only used when EventBus is not provided (backward compatibility).
        """
        self._action_handlers.append(handler)

    def _dispatch_action(self, action: ActionTask) -> None:
        """Dispatch an action to EventBus or registered handlers.

        If EventBus is available, publishes to SERVER_ACTION topic.
        Otherwise, calls registered callback handlers (backward compatibility).
        """
        # New approach: publish to EventBus
        if self._event_bus:
            from .event_bus import Topics
            self._event_bus.publish(Topics.SERVER_ACTION, action)
            return

        # Old approach: call handlers directly (backward compatibility)
        for handler in self._action_handlers:
            try:
                handler(action)
            except Exception as e:
                logger.error(f"Error in action handler: {e}")

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
                    HEADER_DEVICE_AUTH: self._api_key
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
        if not self._server_url or not self._api_key:
            logger.warning("Server URL or API key not configured, skipping trigger")
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
    # WebSocket Client (Actions via Centrifugo)
    # =====================

    def _get_ws_url(self) -> str:
        """Convert HTTP URL to WebSocket URL."""
        parsed = urlparse(self._server_url)

        if parsed.scheme == "https":
            ws_scheme = "wss"
        else:
            ws_scheme = "ws"

        return f"{ws_scheme}://{parsed.netloc}{ENDPOINT_WEBSOCKET}"

    async def _get_token(self) -> str:
        """Token provider for Centrifugo authentication."""
        return self._api_key

    async def connect(self) -> bool:
        """
        Connect to the WebSocket server and subscribe to actions channel.

        Returns:
            True if connected successfully, False otherwise.
        """
        if not self._server_url or not self._api_key:
            logger.warning("Server URL or API key not configured, skipping connection")
            return False

        self._should_reconnect = True

        try:
            ws_url = self._get_ws_url()
            logger.info(f"Connecting to WebSocket: {ws_url}")

            # Create client event handler
            client_handler = ClientHandler(
                on_connected=self._on_ws_connected,
                on_disconnected=self._on_ws_disconnected
            )

            # Create Centrifugo client
            self._ws_client = Client(
                ws_url,
                events=client_handler,
                # get_token=self._get_token,
            )

            # Connect to server
            await self._ws_client.connect()
            logger.info("WebSocket connection initiated")

            # Subscribe to actions channel
            channel = f"device:{self._device_id}:actions"
            sub_handler = ActionSubscriptionHandler(self._dispatch_action)
            self._subscription = self._ws_client.new_subscription(channel, sub_handler)
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
