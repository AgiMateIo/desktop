"""Tests for plugin config validation."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.plugin_base import PluginBase, TriggerPlugin


class TestPluginBaseValidation:
    """Tests for PluginBase validate_config method."""

    def test_default_validation_passes(self, tmp_path):
        """Test that default validation returns True."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        class TestPlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = TestPlugin(plugin_dir)
        valid, error = plugin.validate_config()

        assert valid is True
        assert error == ""

    def test_load_config_calls_validation(self, tmp_path):
        """Test that load_config calls validate_config."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create valid config file
        config_data = {"enabled": True, "value": 42}
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        class TestPlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            def validate_config(self):
                # Custom validation
                value = self._config.get("value", 0)
                if value < 0:
                    return False, "value must be positive"
                return True, ""

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = TestPlugin(plugin_dir)
        result = plugin.load_config()

        assert result == config_data
        assert plugin.enabled is True

    def test_load_config_disables_on_validation_failure(self, tmp_path):
        """Test that plugin is disabled if validation fails."""
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()

        # Create config with invalid value
        config_data = {"enabled": True, "value": -10}
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        class TestPlugin(PluginBase):
            @property
            def name(self):
                return "Test"

            def validate_config(self):
                # Custom validation
                value = self._config.get("value", 0)
                if value < 0:
                    return False, "value must be positive"
                return True, ""

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        plugin = TestPlugin(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False


class TestVisualButtonsValidation:
    """Tests for VisualButtons plugin config validation."""

    def test_valid_config_passes(self, tmp_path):
        """Test that valid config passes validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": 3,
            "buttons": [
                {
                    "button_name": "Test",
                    "trigger_name": "test.trigger",
                    "type": "direct",
                    "params": {}
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        assert plugin.enabled is True
        assert result == config_data

    def test_invalid_grid_columns_string(self, tmp_path):
        """Test that string grid_columns fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": "aa",  # Invalid: string instead of int
            "buttons": []
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False

    def test_invalid_grid_columns_zero(self, tmp_path):
        """Test that zero grid_columns fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": 0,  # Invalid: must be positive
            "buttons": []
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False

    def test_invalid_grid_columns_negative(self, tmp_path):
        """Test that negative grid_columns fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": -5,  # Invalid: must be positive
            "buttons": []
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False

    def test_buttons_not_list(self, tmp_path):
        """Test that non-list buttons fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": 3,
            "buttons": "not a list"  # Invalid: must be list
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False

    def test_button_missing_required_field(self, tmp_path):
        """Test that button missing required field fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": 3,
            "buttons": [
                {
                    "button_name": "Test"
                    # Missing trigger_name and type
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False

    def test_button_invalid_type(self, tmp_path):
        """Test that button with invalid type fails validation."""
        from plugins.triggers.visual_buttons.plugin import VisualButtonsTrigger

        plugin_dir = tmp_path / "visual_buttons"
        plugin_dir.mkdir()

        config_data = {
            "enabled": True,
            "grid_columns": 3,
            "buttons": [
                {
                    "button_name": "Test",
                    "trigger_name": "test.trigger",
                    "type": "invalid_type",  # Invalid: must be 'direct' or 'dialog'
                    "params": {}
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config_data))

        plugin = VisualButtonsTrigger(plugin_dir)
        result = plugin.load_config()

        # Plugin should be disabled
        assert result == {"enabled": False}
        assert plugin.enabled is False
