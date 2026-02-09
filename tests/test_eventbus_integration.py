"""Tests for EventBus integration with components."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from core.event_bus import EventBus, Topics
from core.plugin_manager import PluginManager
from core.server_client import ServerClient
from core.plugin_base import PluginEvent
from core.models import ActionTask
from ui.tray import TrayManager


class TestPluginManagerEventBusIntegration:
    """Tests for PluginManager EventBus integration."""

    def test_plugin_manager_without_event_bus(self, tmp_path):
        """Test PluginManager works without EventBus (backward compatibility)."""
        pm = PluginManager(tmp_path)
        handler_called = []

        pm.on_event(lambda event: handler_called.append(event))

        event = PluginEvent(plugin_id="test", event_name="test.event", data={})
        pm._handle_plugin_event(event)

        assert len(handler_called) == 1
        assert handler_called[0] == event

    def test_plugin_manager_with_event_bus(self, tmp_path):
        """Test PluginManager publishes to EventBus when provided."""
        event_bus = EventBus()
        pm = PluginManager(tmp_path, event_bus=event_bus)

        events_received = []
        event_bus.subscribe(Topics.PLUGIN_EVENT, lambda e: events_received.append(e))

        event = PluginEvent(plugin_id="test", event_name="test.event", data={})
        pm._handle_plugin_event(event)

        assert len(events_received) == 1
        assert events_received[0] == event

    def test_plugin_manager_event_bus_overrides_callbacks(self, tmp_path):
        """Test that EventBus takes precedence over callbacks."""
        event_bus = EventBus()
        pm = PluginManager(tmp_path, event_bus=event_bus)

        # Register old-style callback
        callback_called = []
        pm.on_event(lambda e: callback_called.append(e))

        # Subscribe to EventBus
        bus_events = []
        event_bus.subscribe(Topics.PLUGIN_EVENT, lambda e: bus_events.append(e))

        # Trigger event
        event = PluginEvent(plugin_id="test", event_name="test.event", data={})
        pm._handle_plugin_event(event)

        # Only EventBus should receive event (callbacks ignored)
        assert len(bus_events) == 1
        assert len(callback_called) == 0


class TestServerClientEventBusIntegration:
    """Tests for ServerClient EventBus integration."""

    def test_server_client_without_event_bus(self):
        """Test ServerClient works without EventBus (backward compatibility)."""
        client = ServerClient(
            server_url="http://test.com",
            device_key="test-key",
            device_id="test-device"
        )

        actions_received = []
        client.on_action(lambda a: actions_received.append(a))

        action = ActionTask(type="TEST", parameters={})
        client._dispatch_action(action)

        assert len(actions_received) == 1
        assert actions_received[0] == action

    def test_server_client_with_event_bus(self):
        """Test ServerClient publishes to EventBus when provided."""
        event_bus = EventBus()
        client = ServerClient(
            server_url="http://test.com",
            device_key="test-key",
            device_id="test-device",
            event_bus=event_bus
        )

        actions_received = []
        event_bus.subscribe(Topics.SERVER_ACTION, lambda a: actions_received.append(a))

        action = ActionTask(type="TEST", parameters={})
        client._dispatch_action(action)

        assert len(actions_received) == 1
        assert actions_received[0] == action

    def test_server_client_event_bus_overrides_callbacks(self):
        """Test that EventBus takes precedence over callbacks."""
        event_bus = EventBus()
        client = ServerClient(
            server_url="http://test.com",
            device_key="test-key",
            device_id="test-device",
            event_bus=event_bus
        )

        # Register old-style callback
        callback_called = []
        client.on_action(lambda a: callback_called.append(a))

        # Subscribe to EventBus
        bus_actions = []
        event_bus.subscribe(Topics.SERVER_ACTION, lambda a: bus_actions.append(a))

        # Dispatch action
        action = ActionTask(type="TEST", parameters={})
        client._dispatch_action(action)

        # Only EventBus should receive action (callbacks ignored)
        assert len(bus_actions) == 1
        assert len(callback_called) == 0


# TrayManager tests skipped - requires QApplication fixture which causes segfaults
# TrayManager EventBus integration is tested in the main application via main_new.py


class TestEndToEndEventBusFlow:
    """End-to-end tests for EventBus flow."""

    def test_plugin_to_application_flow(self, tmp_path):
        """Test that plugin events flow through EventBus to application."""
        event_bus = EventBus()
        pm = PluginManager(tmp_path, event_bus=event_bus)

        # Simulate application subscribing to plugin events
        received_events = []
        event_bus.subscribe(Topics.PLUGIN_EVENT, lambda e: received_events.append(e))

        # Simulate plugin emitting event
        event = PluginEvent(plugin_id="test-plugin", event_name="device.test", data={"value": 42})
        pm._handle_plugin_event(event)

        # Application should receive the event
        assert len(received_events) == 1
        assert received_events[0].plugin_id == "test-plugin"
        assert received_events[0].data["value"] == 42

    def test_server_to_application_flow(self):
        """Test that server actions flow through EventBus to application."""
        event_bus = EventBus()
        client = ServerClient(
            server_url="http://test.com",
            device_key="test-key",
            device_id="test-device",
            event_bus=event_bus
        )

        # Simulate application subscribing to server actions
        received_actions = []
        event_bus.subscribe(Topics.SERVER_ACTION, lambda a: received_actions.append(a))

        # Simulate server sending action
        action = ActionTask(type="NOTIFICATION", parameters={"message": "Test"})
        client._dispatch_action(action)

        # Application should receive the action
        assert len(received_actions) == 1
        assert received_actions[0].type == "NOTIFICATION"
        assert received_actions[0].parameters["message"] == "Test"

    # test_ui_to_application_flow skipped - requires QApplication fixture
    # UI flow is tested in the main application via main_new.py
