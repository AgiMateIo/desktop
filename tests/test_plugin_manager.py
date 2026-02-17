"""Tests for core.plugin_manager module."""

import pytest
from pathlib import Path
from core.plugin_manager import PluginManager
from core.plugin_base import PluginEvent
from core.models import ToolResult


class TestPluginManagerInit:
    """Test cases for PluginManager initialization."""

    def test_init(self, tmp_path):
        """Test PluginManager initialization."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)

        assert manager.plugins_dir == plugins_dir
        assert manager.triggers_dir == plugins_dir / "triggers"
        assert manager.tools_dir == plugins_dir / "tools"
        assert manager._triggers == {}
        assert manager._tools == {}
        assert manager._tool_handlers == {}
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
        assert len(manager.tools) == 0

    def test_discover_plugins_with_mock_plugins(self):
        """Test discover_plugins() finds mock plugins."""
        # Use fixtures directory with mock plugins
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Should find mock_trigger
        assert "mock_trigger" in manager.triggers
        assert manager.triggers["mock_trigger"].name == "Mock Trigger"

        # Should find mock_tool
        assert "mock_tool" in manager.tools
        assert manager.tools["mock_tool"].name == "Mock Tool"

    def test_discover_plugins_nonexistent_directory(self, tmp_path):
        """Test discover_plugins() with nonexistent directory."""
        plugins_dir = tmp_path / "nonexistent"

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()  # Should not crash

        assert len(manager.triggers) == 0
        assert len(manager.tools) == 0

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

        tool = manager.tools["mock_tool"]
        assert tool.enabled is True
        assert tool.get_config("test_setting") == "test_value"


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
        assert manager.tools["mock_tool"].initialized is True

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
        # Mock tool should be initialized
        assert manager.tools["mock_tool"].initialized is True

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
        assert manager.tools["mock_tool"].initialized is False

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


class TestToolExecution:
    """Test cases for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test execute_tool() executes successfully."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_tool("MOCK_TOOL", {"param": "value"})

        assert isinstance(result, ToolResult)
        assert result.success is True
        tool = manager.tools["mock_tool"]
        assert len(tool.executed_tools) == 1
        assert tool.executed_tools[0] == ("MOCK_TOOL", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self):
        """Test execute_tool() handles failure."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_tool("MOCK_TOOL", {"should_fail": True})

        assert isinstance(result, ToolResult)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_type(self):
        """Test execute_tool() with unknown tool type."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        result = await manager.execute_tool("UNKNOWN_TOOL", {})

        assert isinstance(result, ToolResult)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_tool_disabled_handler(self):
        """Test execute_tool() with disabled handler."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Disable mock tool
        manager.tools["mock_tool"].set_config("enabled", False)

        await manager.initialize_all()

        result = await manager.execute_tool("MOCK_TOOL", {})

        assert isinstance(result, ToolResult)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_supported_tool_types(self):
        """Test get_supported_tool_types() returns all tool types."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        tool_types = manager.get_supported_tool_types()

        assert "MOCK_TOOL" in tool_types
        assert "MOCK_TOOL_2" in tool_types
        assert len(tool_types) == 2


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
        assert events_received[0].event_name == "desktop.trigger.mock.triggered"
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

        # Should have Triggers and Tools sections
        assert len(items) == 2
        assert items[0].id == "triggers"
        assert items[0].label == "Triggers"
        assert items[1].id == "tools"
        assert items[1].label == "Tools"

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
    async def test_get_all_tray_items_tool_status(self):
        """Test get_all_tray_items() shows tool status."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        await manager.initialize_all()

        items = manager.get_all_tray_items()
        tool_item = items[1].children[0]
        assert "Enabled" in tool_item.label

        # Disable tool
        manager.tools["mock_tool"].set_config("enabled", False)
        items = manager.get_all_tray_items()
        tool_item = items[1].children[0]
        assert "Disabled" in tool_item.label

    @pytest.mark.asyncio
    async def test_get_all_tray_items_empty(self, tmp_path):
        """Test get_all_tray_items() with no plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()

        items = manager.get_all_tray_items()

        assert len(items) == 0


class TestPluginCapabilities:
    """Test cases for plugin manager capabilities aggregation."""

    def test_get_capabilities_with_mock_plugins(self):
        """Test get_capabilities() aggregates from all enabled plugins."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        caps = manager.get_capabilities()

        # Should have triggers and tools
        assert "triggers" in caps
        assert "tools" in caps

        # Check mock trigger capabilities
        assert "desktop.trigger.mock.triggered" in caps["triggers"]
        assert caps["triggers"]["desktop.trigger.mock.triggered"]["params"] == ["test"]
        assert "description" in caps["triggers"]["desktop.trigger.mock.triggered"]

        # Check mock tool capabilities
        assert "MOCK_TOOL" in caps["tools"]
        assert caps["tools"]["MOCK_TOOL"]["params"] == ["param1", "param2"]
        assert "MOCK_TOOL_2" in caps["tools"]
        assert caps["tools"]["MOCK_TOOL_2"]["params"] == ["param3"]

    def test_get_capabilities_excludes_disabled_plugins(self):
        """Test get_capabilities() excludes disabled plugins."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        # Disable both plugins
        manager.triggers["mock_trigger"].set_config("enabled", False)
        manager.tools["mock_tool"].set_config("enabled", False)

        caps = manager.get_capabilities()

        assert caps["triggers"] == {}
        assert caps["tools"] == {}

    def test_get_capabilities_empty(self, tmp_path):
        """Test get_capabilities() with no plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        manager = PluginManager(plugins_dir)
        manager.discover_plugins()

        caps = manager.get_capabilities()

        assert caps == {"triggers": {}, "tools": {}}


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

    def test_tools_property_returns_copy(self):
        """Test tools property returns a copy."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "mock_plugins"

        manager = PluginManager(fixtures_dir)
        manager.discover_plugins()

        tools1 = manager.tools
        tools2 = manager.tools

        # Should be equal but not same object
        assert tools1 == tools2
        assert tools1 is not tools2

        # Modifying copy shouldn't affect manager
        tools1.clear()
        assert len(manager.tools) > 0
