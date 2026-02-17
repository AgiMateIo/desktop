"""Tests for core.plugin_base module."""

import pytest
import json
from pathlib import Path
from core.plugin_base import (
    PluginBase,
    TriggerPlugin,
    ActionPlugin,
    PluginEvent,
    TrayMenuItem
)


class TestPluginEvent:
    """Test cases for PluginEvent dataclass."""

    def test_init(self):
        """Test PluginEvent initialization."""
        event = PluginEvent(
            plugin_id="test_plugin",
            event_name="test.event",
            data={"key": "value"}
        )

        assert event.plugin_id == "test_plugin"
        assert event.event_name == "test.event"
        assert event.data == {"key": "value"}

    def test_init_without_data(self):
        """Test PluginEvent with default empty data."""
        event = PluginEvent(
            plugin_id="test_plugin",
            event_name="test.event"
        )

        assert event.data == {}

    def test_data_is_mutable(self):
        """Test PluginEvent data can be modified."""
        event = PluginEvent(
            plugin_id="test",
            event_name="test",
            data={"original": "value"}
        )

        event.data["new"] = "data"
        assert event.data["new"] == "data"
        assert event.data["original"] == "value"


class TestTrayMenuItem:
    """Test cases for TrayMenuItem dataclass."""

    def test_init_minimal(self):
        """Test TrayMenuItem with minimal parameters."""
        item = TrayMenuItem(
            id="item1",
            label="Test Item"
        )

        assert item.id == "item1"
        assert item.label == "Test Item"
        assert item.callback is None
        assert item.icon is None
        assert item.children == []
        assert item.separator_after is False

    def test_init_with_callback(self):
        """Test TrayMenuItem with callback."""
        def callback():
            pass

        item = TrayMenuItem(
            id="item1",
            label="Test",
            callback=callback
        )

        assert item.callback == callback

    def test_init_with_children(self):
        """Test TrayMenuItem with nested children."""
        child1 = TrayMenuItem(id="child1", label="Child 1")
        child2 = TrayMenuItem(id="child2", label="Child 2")

        parent = TrayMenuItem(
            id="parent",
            label="Parent",
            children=[child1, child2]
        )

        assert len(parent.children) == 2
        assert parent.children[0].id == "child1"
        assert parent.children[1].id == "child2"

    def test_separator_after(self):
        """Test TrayMenuItem with separator."""
        item = TrayMenuItem(
            id="item1",
            label="Test",
            separator_after=True
        )

        assert item.separator_after is True


class TestPluginBase:
    """Test cases for PluginBase abstract class."""

    def test_init(self, tmp_path):
        """Test PluginBase initialization."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create concrete implementation
        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        assert plugin.plugin_dir == plugin_dir
        assert plugin.plugin_id == "test_plugin"
        assert plugin._config == {}
        assert plugin._event_handlers == []

    def test_config_path(self, tmp_path):
        """Test config_path property."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        assert plugin.config_path == plugin_dir / "config.json"

    def test_load_config_nonexistent(self, tmp_path):
        """Test load_config() with nonexistent file."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        result = plugin.load_config()

        # When config file doesn't exist, defaults to enabled
        assert result == {"enabled": True}
        assert plugin._config == {"enabled": True}

    def test_load_config_existing(self, tmp_path):
        """Test load_config() with existing config file."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create config file
        config_data = {"enabled": True, "custom": "value"}
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        result = plugin.load_config()

        assert result == config_data
        assert plugin._config == config_data

    def test_load_config_invalid_json(self, tmp_path):
        """Test load_config() with invalid JSON disables plugin."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create invalid JSON file
        (plugin_dir / "config.json").write_text("{invalid json")

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled on invalid JSON
        assert result == {"enabled": False}
        assert plugin._config == {"enabled": False}
        assert plugin.enabled is False

    def test_load_config_corrupted_file(self, tmp_path):
        """Test load_config() with corrupted file disables plugin."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create file with non-JSON content
        (plugin_dir / "config.json").write_text("not json at all")

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled on corrupted file
        assert result == {"enabled": False}
        assert plugin._config == {"enabled": False}
        assert plugin.enabled is False

    def test_save_config(self, tmp_path):
        """Test save_config() creates file."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        plugin._config = {"test": "data"}
        plugin.save_config()

        config_path = plugin_dir / "config.json"
        assert config_path.exists()

        saved_data = json.loads(config_path.read_text())
        assert saved_data == {"test": "data"}

    def test_get_config(self, tmp_path):
        """Test get_config() method."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        plugin._config = {"key": "value"}

        assert plugin.get_config("key") == "value"
        assert plugin.get_config("nonexistent") is None
        assert plugin.get_config("nonexistent", "default") == "default"

    def test_set_config(self, tmp_path):
        """Test set_config() method."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        plugin.set_config("key", "value")
        assert plugin._config["key"] == "value"

        plugin.set_config("key", "new_value")
        assert plugin._config["key"] == "new_value"

    def test_enabled_property_true(self, tmp_path):
        """Test enabled property returns True."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        plugin._config = {"enabled": True}

        assert plugin.enabled is True

    def test_enabled_property_false(self, tmp_path):
        """Test enabled property returns False."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        plugin._config = {"enabled": False}

        assert plugin.enabled is False

    def test_enabled_property_default_true(self, tmp_path):
        """Test enabled defaults to True if not in config."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)
        plugin._config = {}

        assert plugin.enabled is True


class TestPluginEventSystem:
    """Test cases for plugin event system."""

    def test_on_event_registration(self, tmp_path):
        """Test registering event handler."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        def handler(event):
            pass

        plugin.on_event(handler)

        assert handler in plugin._event_handlers
        assert len(plugin._event_handlers) == 1

    def test_multiple_event_handlers(self, tmp_path):
        """Test registering multiple event handlers."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        handler1 = lambda e: None
        handler2 = lambda e: None

        plugin.on_event(handler1)
        plugin.on_event(handler2)

        assert len(plugin._event_handlers) == 2

    def test_emit_event_calls_handlers(self, tmp_path):
        """Test emit_event() calls all registered handlers."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        events_received = []

        def handler(event):
            events_received.append(event)

        plugin.on_event(handler)
        plugin.emit_event("test.event", {"data": "value"})

        assert len(events_received) == 1
        assert events_received[0].plugin_id == "test_plugin"
        assert events_received[0].event_name == "test.event"
        assert events_received[0].data == {"data": "value"}

    def test_emit_event_without_data(self, tmp_path):
        """Test emit_event() with no data parameter."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))
        plugin.emit_event("test.event")

        assert len(events_received) == 1
        assert events_received[0].data == {}

    def test_emit_event_multiple_handlers(self, tmp_path):
        """Test emit_event() calls all handlers."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class ConcretePlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = ConcretePlugin(plugin_dir)

        calls = {"handler1": 0, "handler2": 0}

        def handler1(event):
            calls["handler1"] += 1

        def handler2(event):
            calls["handler2"] += 1

        plugin.on_event(handler1)
        plugin.on_event(handler2)
        plugin.emit_event("test.event")

        assert calls["handler1"] == 1
        assert calls["handler2"] == 1


class TestTriggerPlugin:
    """Test cases for TriggerPlugin class."""

    def test_init(self, tmp_path):
        """Test TriggerPlugin initialization."""
        plugin_dir = tmp_path / "trigger_plugin"
        plugin_dir.mkdir()

        class ConcreteTrigger(TriggerPlugin):
            @property
            def name(self):
                return "Test Trigger"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

        plugin = ConcreteTrigger(plugin_dir)

        assert plugin._running is False

    def test_running_property(self, tmp_path):
        """Test running property."""
        plugin_dir = tmp_path / "trigger_plugin"
        plugin_dir.mkdir()

        class ConcreteTrigger(TriggerPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def start(self):
                self._running = True

            async def stop(self):
                self._running = False

        plugin = ConcreteTrigger(plugin_dir)

        assert plugin.running is False

        # Simulate start
        plugin._running = True
        assert plugin.running is True

        # Simulate stop
        plugin._running = False
        assert plugin.running is False

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, tmp_path):
        """Test start/stop lifecycle."""
        plugin_dir = tmp_path / "trigger_plugin"
        plugin_dir.mkdir()

        class ConcreteTrigger(TriggerPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def start(self):
                self._running = True

            async def stop(self):
                self._running = False

        plugin = ConcreteTrigger(plugin_dir)

        await plugin.start()
        assert plugin.running is True

        await plugin.stop()
        assert plugin.running is False


class TestTriggerPluginCapabilities:
    """Test cases for TriggerPlugin.get_capabilities()."""

    def test_default_get_capabilities(self, tmp_path):
        """Test default get_capabilities() returns empty dict."""
        plugin_dir = tmp_path / "trigger_plugin"
        plugin_dir.mkdir()

        class ConcreteTrigger(TriggerPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

        plugin = ConcreteTrigger(plugin_dir)
        assert plugin.get_capabilities() == {}

    def test_overridden_get_capabilities(self, tmp_path):
        """Test overridden get_capabilities() returns custom values."""
        plugin_dir = tmp_path / "trigger_plugin"
        plugin_dir.mkdir()

        class ConcreteTrigger(TriggerPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            async def start(self):
                pass

            async def stop(self):
                pass

            def get_capabilities(self):
                return {"device.test.event": ["param1", "param2"]}

        plugin = ConcreteTrigger(plugin_dir)
        caps = plugin.get_capabilities()
        assert caps == {"device.test.event": ["param1", "param2"]}


class TestActionPlugin:
    """Test cases for ActionPlugin class."""

    def test_init(self, tmp_path):
        """Test ActionPlugin initialization."""
        plugin_dir = tmp_path / "action_plugin"
        plugin_dir.mkdir()

        class ConcreteAction(ActionPlugin):
            @property
            def name(self):
                return "Test Action"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            def get_supported_actions(self):
                return ["TEST_ACTION"]

            async def execute(self, action_type, parameters):
                return True

        plugin = ConcreteAction(plugin_dir)

        assert isinstance(plugin, ActionPlugin)

    def test_get_supported_actions(self, tmp_path):
        """Test get_supported_actions() method."""
        plugin_dir = tmp_path / "action_plugin"
        plugin_dir.mkdir()

        class ConcreteAction(ActionPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            def get_supported_actions(self):
                return ["ACTION1", "ACTION2", "ACTION3"]

            async def execute(self, action_type, parameters):
                return True

        plugin = ConcreteAction(plugin_dir)

        actions = plugin.get_supported_actions()
        assert actions == ["ACTION1", "ACTION2", "ACTION3"]

    @pytest.mark.asyncio
    async def test_execute(self, tmp_path):
        """Test execute() method."""
        plugin_dir = tmp_path / "action_plugin"
        plugin_dir.mkdir()

        executed_actions = []

        class ConcreteAction(ActionPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            def get_supported_actions(self):
                return ["TEST"]

            async def execute(self, action_type, parameters):
                executed_actions.append((action_type, parameters))
                return True

        plugin = ConcreteAction(plugin_dir)

        result = await plugin.execute("TEST", {"param": "value"})

        assert result is True
        assert len(executed_actions) == 1
        assert executed_actions[0] == ("TEST", {"param": "value"})


class TestActionPluginCapabilities:
    """Test cases for ActionPlugin.get_capabilities()."""

    def test_default_get_capabilities(self, tmp_path):
        """Test default get_capabilities() returns actions with empty params."""
        plugin_dir = tmp_path / "action_plugin"
        plugin_dir.mkdir()

        class ConcreteAction(ActionPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            def get_supported_actions(self):
                return ["ACTION_A", "ACTION_B"]

            async def execute(self, action_type, parameters):
                return True

        plugin = ConcreteAction(plugin_dir)
        caps = plugin.get_capabilities()
        assert caps == {
            "ACTION_A": {"params": [], "description": ""},
            "ACTION_B": {"params": [], "description": ""},
        }

    def test_overridden_get_capabilities(self, tmp_path):
        """Test overridden get_capabilities() returns custom values."""
        plugin_dir = tmp_path / "action_plugin"
        plugin_dir.mkdir()

        class ConcreteAction(ActionPlugin):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

            def get_supported_actions(self):
                return ["ACTION_A"]

            async def execute(self, action_type, parameters):
                return True

            def get_capabilities(self):
                return {"ACTION_A": ["param1", "param2"]}

        plugin = ConcreteAction(plugin_dir)
        caps = plugin.get_capabilities()
        assert caps == {"ACTION_A": ["param1", "param2"]}
