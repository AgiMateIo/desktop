"""Server client for HTTP triggers and WebSocket actions."""

import asyncio
import logging
from typing import Any, Callable
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

    async def on_subscribed(self, ctx: SubscribedContext) -> None:
        logger.info(f"Subscribed to channel: {ctx.channel}")

    async def on_publication(self, ctx: PublicationContext) -> None:
        """Handle incoming publication (action from server)."""
        try:
            data = ctx.pub.data
            logger.info(f"Received action: {data}")
            action = ActionTask.from_dict(data)
            # Use asyncio.ensure_future to not block the read loop
            asyncio.ensure_future(self._handle_action(action))
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
        reconnect_interval: int = 5000
    ):
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._device_id = device_id
        self._reconnect_interval = reconnect_interval / 1000  # Convert to seconds

        self._http_session: aiohttp.ClientSession | None = None
        self._ws_client: Client | None = None
        self._subscription = None
        self._connected = False
        self._action_handlers: list[Callable[[ActionTask], None]] = []
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect = False

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected

    @property
    def server_url(self) -> str:
        """Get the server URL."""
        return self._server_url

    def on_action(self, handler: Callable[[ActionTask], None]) -> None:
        """Register a handler for incoming actions."""
        self._action_handlers.append(handler)

    def _dispatch_action(self, action: ActionTask) -> None:
        """Dispatch an action to all handlers."""
        for handler in self._action_handlers:
            try:
                handler(action)
            except Exception as e:
                logger.error(f"Error in action handler: {e}")

    def _on_ws_connected(self) -> None:
        """Called when WebSocket connects."""
        self._connected = True

    def _on_ws_disconnected(self) -> None:
        """Called when WebSocket disconnects."""
        self._connected = False
        self._schedule_reconnect()

    # =====================
    # HTTP Client (Triggers)
    # =====================

    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        """Ensure HTTP session exists."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/json",
                    "X-Device-Auth-Key": self._api_key
                }
            )
        return self._http_session

    async def send_trigger(self, payload: TriggerPayload) -> bool:
        """
        Send a trigger event to the server.

        Args:
            payload: The trigger payload to send.

        Returns:
            True if the trigger was sent successfully, False otherwise.
        """
        if not self._server_url or not self._api_key:
            logger.warning("Server URL or API key not configured, skipping trigger")
            return False

        url = f"{self._server_url}/mobile-api/device/trigger/new"

        try:
            session = await self._ensure_http_session()
            async with session.post(url, json=payload.to_dict()) as response:
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

        return f"{ws_scheme}://{parsed.netloc}/connection/websocket"

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
            logger.info(f"Subscribed to channel: {channel}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self._connected = False
            self._schedule_reconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False

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
        """Schedule a reconnection attempt."""
        if not self._should_reconnect:
            return

        if self._reconnect_task and not self._reconnect_task.done():
            return

        async def reconnect():
            await asyncio.sleep(self._reconnect_interval)
            if self._should_reconnect:
                logger.info("Attempting to reconnect...")
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
