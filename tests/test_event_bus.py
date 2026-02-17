"""Tests for event bus."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from core.event_bus import EventBus, Topics, Event


class TestEventBusInit:
    """Tests for EventBus initialization."""

    def test_init(self):
        bus = EventBus()
        assert bus._sync_handlers == {}
        assert bus._async_handlers == {}


class TestSyncSubscribe:
    """Tests for synchronous subscription."""

    def test_subscribe_handler(self):
        bus = EventBus()
        handler = MagicMock()

        bus.subscribe("test.topic", handler)

        assert "test.topic" in bus._sync_handlers
        assert handler in bus._sync_handlers["test.topic"]

    def test_subscribe_multiple_handlers(self):
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe("test.topic", handler1)
        bus.subscribe("test.topic", handler2)

        assert len(bus._sync_handlers["test.topic"]) == 2
        assert handler1 in bus._sync_handlers["test.topic"]
        assert handler2 in bus._sync_handlers["test.topic"]

    def test_subscribe_different_topics(self):
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe("topic1", handler1)
        bus.subscribe("topic2", handler2)

        assert "topic1" in bus._sync_handlers
        assert "topic2" in bus._sync_handlers
        assert handler1 in bus._sync_handlers["topic1"]
        assert handler2 in bus._sync_handlers["topic2"]


class TestAsyncSubscribe:
    """Tests for asynchronous subscription."""

    def test_subscribe_async_handler(self):
        bus = EventBus()
        handler = AsyncMock()

        bus.subscribe_async("test.topic", handler)

        assert "test.topic" in bus._async_handlers
        assert handler in bus._async_handlers["test.topic"]

    def test_subscribe_multiple_async_handlers(self):
        bus = EventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        bus.subscribe_async("test.topic", handler1)
        bus.subscribe_async("test.topic", handler2)

        assert len(bus._async_handlers["test.topic"]) == 2
        assert handler1 in bus._async_handlers["test.topic"]
        assert handler2 in bus._async_handlers["test.topic"]


class TestUnsubscribe:
    """Tests for unsubscription."""

    def test_unsubscribe_sync_handler(self):
        bus = EventBus()
        handler = MagicMock()

        bus.subscribe("test.topic", handler)
        bus.unsubscribe("test.topic", handler)

        assert handler not in bus._sync_handlers.get("test.topic", [])

    def test_unsubscribe_async_handler(self):
        bus = EventBus()
        handler = AsyncMock()

        bus.subscribe_async("test.topic", handler)
        bus.unsubscribe("test.topic", handler)

        assert handler not in bus._async_handlers.get("test.topic", [])

    def test_unsubscribe_nonexistent_handler(self):
        bus = EventBus()
        handler = MagicMock()

        # Should not raise error
        bus.unsubscribe("test.topic", handler)


class TestPublish:
    """Tests for synchronous publishing."""

    def test_publish_calls_handler(self):
        bus = EventBus()
        handler = MagicMock()
        bus.subscribe("test.topic", handler)

        bus.publish("test.topic", {"key": "value"})

        handler.assert_called_once_with({"key": "value"})

    def test_publish_calls_multiple_handlers(self):
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = MagicMock()
        bus.subscribe("test.topic", handler1)
        bus.subscribe("test.topic", handler2)

        bus.publish("test.topic", "data")

        handler1.assert_called_once_with("data")
        handler2.assert_called_once_with("data")

    def test_publish_no_subscribers(self):
        bus = EventBus()

        # Should not raise error
        bus.publish("test.topic", "data")

    def test_publish_without_data(self):
        bus = EventBus()
        handler = MagicMock()
        bus.subscribe("test.topic", handler)

        bus.publish("test.topic")

        handler.assert_called_once_with(None)

    def test_publish_handler_exception(self):
        bus = EventBus()
        handler = MagicMock(side_effect=ValueError("test error"))
        bus.subscribe("test.topic", handler)

        # Should not raise, should log error
        bus.publish("test.topic", "data")

        handler.assert_called_once()


class TestPublishAsync:
    """Tests for asynchronous publishing."""

    @pytest.mark.asyncio
    async def test_publish_async_calls_handler(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe_async("test.topic", handler)

        await bus.publish_async("test.topic", {"key": "value"})

        handler.assert_called_once_with({"key": "value"})

    @pytest.mark.asyncio
    async def test_publish_async_calls_multiple_handlers(self):
        bus = EventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        bus.subscribe_async("test.topic", handler1)
        bus.subscribe_async("test.topic", handler2)

        await bus.publish_async("test.topic", "data")

        handler1.assert_called_once_with("data")
        handler2.assert_called_once_with("data")

    @pytest.mark.asyncio
    async def test_publish_async_no_subscribers(self):
        bus = EventBus()

        # Should not raise error
        await bus.publish_async("test.topic", "data")

    @pytest.mark.asyncio
    async def test_publish_async_handler_exception(self):
        bus = EventBus()
        handler = AsyncMock(side_effect=ValueError("test error"))
        bus.subscribe_async("test.topic", handler)

        # Should not raise, should log error
        await bus.publish_async("test.topic", "data")

        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_async_concurrent_execution(self):
        """Test that async handlers run concurrently."""
        bus = EventBus()
        call_order = []

        async def slow_handler(data):
            call_order.append("slow_start")
            await asyncio.sleep(0.1)
            call_order.append("slow_end")

        async def fast_handler(data):
            call_order.append("fast")

        bus.subscribe_async("test.topic", slow_handler)
        bus.subscribe_async("test.topic", fast_handler)

        await bus.publish_async("test.topic", "data")

        # Fast handler should complete before slow handler ends
        assert "fast" in call_order
        assert call_order.index("fast") < call_order.index("slow_end")


class TestClear:
    """Tests for clearing handlers."""

    def test_clear_specific_topic(self):
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = MagicMock()
        bus.subscribe("topic1", handler1)
        bus.subscribe("topic2", handler2)

        bus.clear("topic1")

        assert "topic1" not in bus._sync_handlers
        assert "topic2" in bus._sync_handlers

    def test_clear_all_topics(self):
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = AsyncMock()
        bus.subscribe("topic1", handler1)
        bus.subscribe_async("topic2", handler2)

        bus.clear()

        assert bus._sync_handlers == {}
        assert bus._async_handlers == {}

    def test_clear_nonexistent_topic(self):
        bus = EventBus()

        # Should not raise error
        bus.clear("nonexistent")


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_subscriber_count_empty(self):
        bus = EventBus()
        assert bus.get_subscriber_count("test.topic") == 0

    def test_get_subscriber_count_sync_only(self):
        bus = EventBus()
        bus.subscribe("test.topic", MagicMock())
        bus.subscribe("test.topic", MagicMock())

        assert bus.get_subscriber_count("test.topic") == 2

    def test_get_subscriber_count_async_only(self):
        bus = EventBus()
        bus.subscribe_async("test.topic", AsyncMock())
        bus.subscribe_async("test.topic", AsyncMock())

        assert bus.get_subscriber_count("test.topic") == 2

    def test_get_subscriber_count_mixed(self):
        bus = EventBus()
        bus.subscribe("test.topic", MagicMock())
        bus.subscribe_async("test.topic", AsyncMock())

        assert bus.get_subscriber_count("test.topic") == 2

    def test_get_all_topics_empty(self):
        bus = EventBus()
        assert bus.get_all_topics() == []

    def test_get_all_topics_with_subscribers(self):
        bus = EventBus()
        bus.subscribe("topic1", MagicMock())
        bus.subscribe_async("topic2", AsyncMock())
        bus.subscribe("topic3", MagicMock())

        topics = bus.get_all_topics()
        assert sorted(topics) == ["topic1", "topic2", "topic3"]


class TestTopicsConstants:
    """Tests for Topics constants."""

    def test_topics_defined(self):
        assert hasattr(Topics, "PLUGIN_EVENT")
        assert hasattr(Topics, "SERVER_TOOL")
        assert hasattr(Topics, "UI_QUIT_REQUESTED")
        assert hasattr(Topics, "UI_SETTINGS_REQUESTED")

    def test_topics_are_strings(self):
        assert isinstance(Topics.PLUGIN_EVENT, str)
        assert isinstance(Topics.SERVER_TOOL, str)
        assert isinstance(Topics.UI_QUIT_REQUESTED, str)


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        event = Event(topic="test.topic", data={"key": "value"})

        assert event.topic == "test.topic"
        assert event.data == {"key": "value"}

    def test_event_default_data(self):
        event = Event(topic="test.topic")

        assert event.topic == "test.topic"
        assert event.data is None


class TestIntegration:
    """Integration tests for EventBus."""

    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self):
        """Test that sync and async handlers can coexist."""
        bus = EventBus()
        sync_called = []
        async_called = []

        def sync_handler(data):
            sync_called.append(data)

        async def async_handler(data):
            async_called.append(data)

        bus.subscribe("test.topic", sync_handler)
        bus.subscribe_async("test.topic", async_handler)

        bus.publish("test.topic", "sync_data")
        await bus.publish_async("test.topic", "async_data")

        assert sync_called == ["sync_data"]
        assert async_called == ["async_data"]

    def test_multiple_topics_isolation(self):
        """Test that topics are isolated from each other."""
        bus = EventBus()
        handler1 = MagicMock()
        handler2 = MagicMock()

        bus.subscribe("topic1", handler1)
        bus.subscribe("topic2", handler2)

        bus.publish("topic1", "data1")

        handler1.assert_called_once_with("data1")
        handler2.assert_not_called()
