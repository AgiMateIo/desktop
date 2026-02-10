"""Tests for visual_buttons trigger plugin."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from .plugin import VisualButtonsTrigger


class TestVisualButtonsInit:
    """Test cases for VisualButtonsTrigger initialization."""

    def test_init(self, tmp_path):
        """Test VisualButtonsTrigger initialization."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        assert plugin.plugin_dir == plugin_dir
        assert plugin.plugin_id == "visual_buttons"
        assert plugin.name == "Visual Buttons"

    def test_load_config_with_buttons(self, tmp_path):
        """Test loading plugin configuration with buttons."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "grid_columns": 3,
            "buttons": [
                {
                    "button_name": "Test Button",
                    "trigger_name": "desktop.trigger.visualbuttons.test",
                    "type": "direct",
                    "params": {"key": "value"}
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        assert plugin.enabled is True
        assert plugin.get_config("grid_columns") == 3
        assert len(plugin.get_config("buttons")) == 1
        assert plugin.get_config("buttons")[0]["button_name"] == "Test Button"


class TestVisualButtonsLifecycle:
    """Test cases for plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize(self, tmp_path):
        """Test initialize() method."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        await plugin.initialize()

        # Should not crash

    @pytest.mark.asyncio
    async def test_shutdown(self, tmp_path):
        """Test shutdown() method."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        await plugin.initialize()
        await plugin.shutdown()

        # Should not crash

    @pytest.mark.asyncio
    async def test_start(self, tmp_path):
        """Test start() method."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)
        await plugin.initialize()

        await plugin.start()

        assert plugin.running is True

    @pytest.mark.asyncio
    async def test_stop(self, tmp_path):
        """Test stop() method."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)
        await plugin.initialize()

        await plugin.start()
        await plugin.stop()

        assert plugin.running is False


class TestButtonConfiguration:
    """Test cases for button configuration."""

    def test_load_empty_buttons(self, tmp_path):
        """Test loading with no buttons configured."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        buttons = plugin.get_config("buttons", [])
        assert buttons == []

    def test_load_multiple_buttons(self, tmp_path):
        """Test loading multiple buttons."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "buttons": [
                {
                    "button_name": "Button 1",
                    "trigger_name": "desktop.trigger.visualbuttons.1",
                    "type": "direct",
                    "params": {}
                },
                {
                    "button_name": "Button 2",
                    "trigger_name": "desktop.trigger.visualbuttons.2",
                    "type": "dialog",
                    "params": {},
                    "dialog_params": {
                        "input_label": "Input",
                        "input_type": "text"
                    }
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        buttons = plugin.get_config("buttons")
        assert len(buttons) == 2
        assert buttons[0]["type"] == "direct"
        assert buttons[1]["type"] == "dialog"

    def test_default_grid_columns(self, tmp_path):
        """Test default grid columns value."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        grid_columns = plugin.get_config("grid_columns", 3)
        assert grid_columns == 3


class TestButtonWindow:
    """Test cases for button window functionality."""

    def test_has_window(self, tmp_path):
        """Test has_window() returns True."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        assert plugin.has_window() is True

    def test_create_window(self, tmp_path):
        """Test create_window() creates window."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        with patch('plugins.triggers.visual_buttons.plugin.VisualButtonsWindow') as MockWindow:
            mock_window = MagicMock()
            MockWindow.return_value = mock_window

            window = plugin.create_window()

            assert window is not None
            MockWindow.assert_called_once_with(plugin, None)



class TestEventEmission:
    """Test cases for event emission."""

    def test_emit_button_event(self, tmp_path):
        """Test emitting button event."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))

        # Emit event
        plugin.emit_event("desktop.trigger.visualbuttons.test", {"button": "test"})

        assert len(events_received) == 1
        assert events_received[0].event_name == "desktop.trigger.visualbuttons.test"
        assert events_received[0].data == {"button": "test"}

    def test_emit_button_event_with_user_input(self, tmp_path):
        """Test emitting button event with user input."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))

        # Emit event with user input
        plugin.emit_event("desktop.trigger.visualbuttons.note", {
            "button_name": "Quick Note",
            "user_input": "Test note content"
        })

        assert len(events_received) == 1
        assert events_received[0].data["user_input"] == "Test note content"


class TestTrayMenuItems:
    """Test cases for tray menu items."""

    def test_get_tray_menu_items(self, tmp_path):
        """Test get_tray_menu_items() returns list (inherited from base)."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        items = plugin.get_tray_menu_items()

        # Plugin doesn't override this, so it uses base class implementation
        assert isinstance(items, list)


class TestButtonTypes:
    """Test cases for different button types."""

    def test_direct_button_config(self, tmp_path):
        """Test direct button configuration."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "buttons": [
                {
                    "button_name": "Direct Button",
                    "trigger_name": "desktop.trigger.visualbuttons.direct",
                    "type": "direct",
                    "params": {"immediate": True}
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        button = plugin.get_config("buttons")[0]
        assert button["type"] == "direct"
        assert button["params"]["immediate"] is True

    def test_dialog_button_config(self, tmp_path):
        """Test dialog button configuration."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "buttons": [
                {
                    "button_name": "Dialog Button",
                    "trigger_name": "desktop.trigger.visualbuttons.dialog",
                    "type": "dialog",
                    "params": {},
                    "dialog_params": {
                        "input_label": "Enter text",
                        "input_type": "textarea",
                        "placeholder": "Type here..."
                    }
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = VisualButtonsTrigger(plugin_dir)
        plugin.load_config()

        button = plugin.get_config("buttons")[0]
        assert button["type"] == "dialog"
        assert button["dialog_params"]["input_label"] == "Enter text"
        assert button["dialog_params"]["input_type"] == "textarea"


class TestConfigPersistence:
    """Test cases for config persistence."""

    def test_save_button_config(self, tmp_path):
        """Test saving button configuration."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        # Set new button config
        new_buttons = [
            {
                "button_name": "New Button",
                "trigger_name": "desktop.trigger.visualbuttons.new",
                "type": "direct",
                "params": {}
            }
        ]
        plugin.set_config("buttons", new_buttons)
        plugin.save_config()

        # Load in new instance
        plugin2 = VisualButtonsTrigger(plugin_dir)
        plugin2.load_config()

        loaded_buttons = plugin2.get_config("buttons")
        assert len(loaded_buttons) == 1
        assert loaded_buttons[0]["button_name"] == "New Button"

    def test_update_grid_columns(self, tmp_path):
        """Test updating grid columns configuration."""
        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        plugin = VisualButtonsTrigger(plugin_dir)

        plugin.set_config("grid_columns", 4)
        plugin.save_config()

        plugin2 = VisualButtonsTrigger(plugin_dir)
        plugin2.load_config()

        assert plugin2.get_config("grid_columns") == 4
