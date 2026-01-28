"""Event bus for pub/sub communication between components.

Replaces direct callback wiring with a decoupled event system.
"""

import asyncio
import logging
from typing import Any, Callable
from dataclasses import dataclass


logger = logging.getLogger(__name__)


class Topics:
    """Event topic constants."""

    # Plugin events
    PLUGIN_EVENT = "plugin.event"

    # Server events
    SERVER_ACTION = "server.action"
    SERVER_CONNECTED = "server.connected"
    SERVER_DISCONNECTED = "server.disconnected"

    # UI events
    UI_QUIT_REQUESTED = "ui.quit.requested"
    UI_SETTINGS_REQUESTED = "ui.settings.requested"
    UI_SETTINGS_CHANGED = "ui.settings.changed"

    # Application lifecycle
    APP_INITIALIZED = "app.initialized"
    APP_SHUTDOWN = "app.shutdown"


@dataclass
class Event:
    """Event data container."""
    topic: str
    data: Any = None


class EventBus:
    """
    Simple pub/sub event bus for decoupled communication.

    Supports both synchronous and asynchronous handlers.
    """

    def __init__(self):
        self._sync_handlers: dict[str, list[Callable]] = {}
        self._async_handlers: dict[str, list[Callable]] = {}

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        """
        Subscribe a synchronous handler to a topic.

        Args:
            topic: Event topic to subscribe to
            handler: Synchronous function to call when event is published
        """
        if topic not in self._sync_handlers:
            self._sync_handlers[topic] = []

        self._sync_handlers[topic].append(handler)
        logger.debug(f"Subscribed sync handler to topic: {topic}")

    def subscribe_async(self, topic: str, handler: Callable[[Any], None]) -> None:
        """
        Subscribe an asynchronous handler to a topic.

        Args:
            topic: Event topic to subscribe to
            handler: Async function to call when event is published
        """
        if topic not in self._async_handlers:
            self._async_handlers[topic] = []

        self._async_handlers[topic].append(handler)
        logger.debug(f"Subscribed async handler to topic: {topic}")

    def unsubscribe(self, topic: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from a topic.

        Args:
            topic: Event topic to unsubscribe from
            handler: Handler to remove
        """
        if topic in self._sync_handlers:
            try:
                self._sync_handlers[topic].remove(handler)
                logger.debug(f"Unsubscribed sync handler from topic: {topic}")
            except ValueError:
                pass

        if topic in self._async_handlers:
            try:
                self._async_handlers[topic].remove(handler)
                logger.debug(f"Unsubscribed async handler from topic: {topic}")
            except ValueError:
                pass

    def publish(self, topic: str, data: Any = None) -> None:
        """
        Publish an event to all synchronous subscribers.

        Args:
            topic: Event topic
            data: Event data to pass to handlers
        """
        if topic not in self._sync_handlers:
            return

        logger.debug(f"Publishing to topic: {topic}")

        for handler in self._sync_handlers[topic]:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in sync handler for topic '{topic}': {e}")

    async def publish_async(self, topic: str, data: Any = None) -> None:
        """
        Publish an event to all asynchronous subscribers.

        Args:
            topic: Event topic
            data: Event data to pass to handlers
        """
        if topic not in self._async_handlers:
            return

        logger.debug(f"Publishing async to topic: {topic}")

        # Run all async handlers concurrently
        tasks = []
        for handler in self._async_handlers[topic]:
            try:
                task = asyncio.create_task(handler(data))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task for topic '{topic}': {e}")

        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error in async handler for topic '{topic}': {result}")

    def clear(self, topic: str | None = None) -> None:
        """
        Clear all handlers for a topic, or all topics if topic is None.

        Args:
            topic: Topic to clear, or None to clear all
        """
        if topic is None:
            self._sync_handlers.clear()
            self._async_handlers.clear()
            logger.debug("Cleared all event handlers")
        else:
            if topic in self._sync_handlers:
                del self._sync_handlers[topic]
            if topic in self._async_handlers:
                del self._async_handlers[topic]
            logger.debug(f"Cleared handlers for topic: {topic}")

    def get_subscriber_count(self, topic: str) -> int:
        """
        Get the number of subscribers for a topic.

        Args:
            topic: Topic to check

        Returns:
            Total number of subscribers (sync + async)
        """
        sync_count = len(self._sync_handlers.get(topic, []))
        async_count = len(self._async_handlers.get(topic, []))
        return sync_count + async_count

    def get_all_topics(self) -> list[str]:
        """
        Get all topics with subscribers.

        Returns:
            List of topic names
        """
        topics = set(self._sync_handlers.keys()) | set(self._async_handlers.keys())
        return sorted(topics)
