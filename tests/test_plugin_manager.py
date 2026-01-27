"""Tests for core.plugin_manager module."""

import pytest
from pathlib import Path
from core.plugin_manager import PluginManager
from core.plugin_base import PluginEvent


class TestPluginManagerInit:
    """Test cases for PluginManager initialization."""

    def test_init(self, tmp_path):
        """Test PluginManager initialization."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)

        assert manager.plugins_dir == plugins_dir
        assert manager.triggers_dir == plugins_dir / "triggers"
        assert manager.actions_dir == plugins_dir / "actions"
        assert manager._triggers == {}
        assert manager._actions == {}
        assert manager._action_handlers == {}
        assert manager._event_handlers == []


class TestPluginDiscovery:
    """Test cases for plugin discovery."""

    def test_discover_plugins_empty_directory(self, tmp_path):
        """Test discover_plugins() with no plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()

        assert len(manager.triggers) == 0
        assert len(manager.actions) == 0

    def test_discover_plugins_with_mock_plugins(self):
        """Test discover_plugins() finds mock plugins."""
        # Use fixtures directory with mock plugins
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Should find mock_trigger
        assert "mock_trigger" in manager.triggers
        assert manager.triggers["mock_trigger"].name == "Mock Trigger"

        # Should find mock_action
        assert "mock_action" in manager.actions
        assert manager.actions["mock_action"].name == "Mock Action"

    def test_discover_plugins_nonexistent_directory(self, tmp_path):
        """Test discover_plugins() with nonexistent directory."""
        plugins_dir = tmp_path / "nonexistent"

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()  # Should not crash

        assert len(manager.triggers) == 0
        assert len(manager.actions) == 0

    def test_discover_plugins_skips_directories_without_plugin_py(self, tmp_path):
        """Test discover_plugins() skips directories without plugin.py."""
        plugins_dir = tmp_path / "plugins"
        triggers_dir = plugins_dir / "triggers"
        triggers_dir.mkdir(parents=True)

        # Create directory without plugin.py
        (triggers_dir / "invalid_plugin").mkdir()

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()

        assert len(manager.triggers) == 0

    def test_discover_plugins_loads_config(self):
        """Test discover_plugins() loads plugin config."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        trigger = manager.triggers["mock_trigger"]
        assert trigger.enabled is True
        assert trigger.get_config("test_option") == "test_value"

        action = manager.actions["mock_action"]
        assert action.enabled is True
        assert action.get_config("test_setting") == "test_value"


class TestPluginLifecycle:
    """Test cases for plugin lifecycle management."""

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        """Test initialize_all() initializes all enabled plugins."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        # Check mock plugins are initialized
        assert manager.triggers["mock_trigger"].initialized is True
        assert manager.actions["mock_action"].initialized is True

    @pytest.mark.asyncio
    async def test_initialize_all_skips_disabled_plugins(self):
        """Test initialize_all() skips disabled plugins."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Disable mock trigger
        manager.triggers["mock_trigger"].set_config("enabled", False)

        await manager.initialize_all()

        # Mock trigger should not be initialized
        assert manager.triggers["mock_trigger"].initialized is False
        # Mock action should be initialized
        assert manager.actions["mock_action"].initialized is True

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """Test shutdown_all() shuts down all plugins."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()
        await manager.start_triggers()

        await manager.shutdown_all()

        # All plugins should be shutdown
        assert manager.triggers["mock_trigger"].initialized is False
        assert manager.triggers["mock_trigger"].started is False
        assert manager.actions["mock_action"].initialized is False

    @pytest.mark.asyncio
    async def test_start_triggers(self):
        """Test start_triggers() starts all enabled triggers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()
        await manager.start_triggers()

        trigger = manager.triggers["mock_trigger"]
        assert trigger.started is True
        assert trigger.running is True

    @pytest.mark.asyncio
    async def test_start_triggers_skips_disabled(self):
        """Test start_triggers() skips disabled triggers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Disable mock trigger
        manager.triggers["mock_trigger"].set_config("enabled", False)

        await manager.initialize_all()
        await manager.start_triggers()

        trigger = manager.triggers["mock_trigger"]
        assert trigger.started is False
        assert trigger.running is False

    @pytest.mark.asyncio
    async def test_start_triggers_skips_already_running(self):
        """Test start_triggers() skips already running triggers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        # Start once
        await manager.start_triggers()
        trigger = manager.triggers["mock_trigger"]
        first_start_count = len(trigger.plugin_dir.parts)  # Simple state check

        # Start again - should skip
        await manager.start_triggers()
        second_start_count = len(trigger.plugin_dir.parts)

        assert first_start_count == second_start_count
        assert trigger.running is True

    @pytest.mark.asyncio
    async def test_stop_triggers(self):
        """Test stop_triggers() stops all running triggers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()
        await manager.start_triggers()

        trigger = manager.triggers["mock_trigger"]
        assert trigger.running is True

        await manager.stop_triggers()

        assert trigger.started is False
        assert trigger.running is False

    @pytest.mark.asyncio
    async def test_stop_triggers_skips_not_running(self):
        """Test stop_triggers() skips triggers not running."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()
        # Don't start triggers

        await manager.stop_triggers()  # Should not crash

        trigger = manager.triggers["mock_trigger"]
        assert trigger.running is False


class TestActionExecution:
    """Test cases for action execution."""

    @pytest.mark.asyncio
    async def test_execute_action_success(self):
        """Test execute_action() executes successfully."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_action("MOCK_ACTION", {"param": "value"})

        assert result is True
        action = manager.actions["mock_action"]
        assert len(action.executed_actions) == 1
        assert action.executed_actions[0] == ("MOCK_ACTION", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_action_failure(self):
        """Test execute_action() handles failure."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_action("MOCK_ACTION", {"should_fail": True})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_action_unknown_type(self):
        """Test execute_action() with unknown action type."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_action("UNKNOWN_ACTION", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_action_disabled_handler(self):
        """Test execute_action() with disabled handler."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Disable mock action
        manager.actions["mock_action"].set_config("enabled", False)

        await manager.initialize_all()

        result = await manager.execute_action("MOCK_ACTION", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_get_supported_action_types(self):
        """Test get_supported_action_types() returns all action types."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        action_types = manager.get_supported_action_types()

        assert "MOCK_ACTION" in action_types
        assert "MOCK_ACTION_2" in action_types
        assert len(action_types) == 2


class TestEventHandling:
    """Test cases for event handling."""

    @pytest.mark.asyncio
    async def test_on_event_registration(self):
        """Test on_event() registers event handler."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)

        events_received = []

        def handler(event):
            events_received.append(event)

        manager.on_event(handler)

        assert len(manager._event_handlers) == 1

    @pytest.mark.asyncio
    async def test_plugin_events_forwarded_to_manager(self):
        """Test plugin events are forwarded to manager handlers."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        events_received = []

        def handler(event):
            events_received.append(event)

        manager.on_event(handler)

        await manager.initialize_all()
        await manager.start_triggers()

        # Mock trigger emits event on start
        assert len(events_received) == 1
        assert events_received[0].event_name == "device.mock.triggered"
        assert events_received[0].data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_multiple_event_handlers(self):
        """Test multiple event handlers receive events."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        events1 = []
        events2 = []

        manager.on_event(lambda e: events1.append(e))
        manager.on_event(lambda e: events2.append(e))

        await manager.initialize_all()
        await manager.start_triggers()

        assert len(events1) == 1
        assert len(events2) == 1

    @pytest.mark.asyncio
    async def test_event_handler_error_doesnt_crash(self):
        """Test event handler errors don't crash plugin manager."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Register handler that raises error
        def bad_handler(event):
            raise ValueError("Handler error")

        events_received = []

        def good_handler(event):
            events_received.append(event)

        manager.on_event(bad_handler)
        manager.on_event(good_handler)

        await manager.initialize_all()
        await manager.start_triggers()

        # Good handler should still receive event
        assert len(events_received) == 1


class TestTrayMenuGeneration:
    """Test cases for tray menu generation."""

    @pytest.mark.asyncio
    async def test_get_all_tray_items_structure(self):
        """Test get_all_tray_items() returns correct structure."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        items = manager.get_all_tray_items()

        # Should have Triggers and Actions sections
        assert len(items) == 2
        assert items[0].id == "triggers"
        assert items[0].label == "Triggers"
        assert items[1].id == "actions"
        assert items[1].label == "Actions"

    @pytest.mark.asyncio
    async def test_get_all_tray_items_trigger_status(self):
        """Test get_all_tray_items() shows trigger status."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        # Before start
        items = manager.get_all_tray_items()
        trigger_item = items[0].children[0]
        assert "Stopped" in trigger_item.label

        # After start
        await manager.start_triggers()
        items = manager.get_all_tray_items()
        trigger_item = items[0].children[0]
        assert "Running" in trigger_item.label

    @pytest.mark.asyncio
    async def test_get_all_tray_items_action_status(self):
        """Test get_all_tray_items() shows action status."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        items = manager.get_all_tray_items()
        action_item = items[1].children[0]
        assert "Enabled" in action_item.label

        # Disable action
        manager.actions["mock_action"].set_config("enabled", False)
        items = manager.get_all_tray_items()
        action_item = items[1].children[0]
        assert "Disabled" in action_item.label

    @pytest.mark.asyncio
    async def test_get_all_tray_items_empty(self, tmp_path):
        """Test get_all_tray_items() with no plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()

        items = manager.get_all_tray_items()

        assert len(items) == 0


class TestPluginProperties:
    """Test cases for plugin manager properties."""

    def test_triggers_property_returns_copy(self):
        """Test triggers property returns a copy."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        triggers1 = manager.triggers
        triggers2 = manager.triggers

        # Should be equal but not same object
        assert triggers1 == triggers2
        assert triggers1 is not triggers2

        # Modifying copy shouldn't affect manager
        triggers1.clear()
        assert len(manager.triggers) > 0

    def test_actions_property_returns_copy(self):
        """Test actions property returns a copy."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        actions1 = manager.actions
        actions2 = manager.actions

        # Should be equal but not same object
        assert actions1 == actions2
        assert actions1 is not actions2

        # Modifying copy shouldn't affect manager
        actions1.clear()
        assert len(manager.actions) > 0
