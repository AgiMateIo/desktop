"""Tests for core.config_manager module."""

import pytest
import json
from pathlib import Path
from core.config_manager import ConfigManager


class TestConfigManagerInit:
    """Test cases for ConfigManager initialization."""

    def test_init(self, tmp_path):
        """Test ConfigManager initialization."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        assert config.config_path == config_path
        assert config._config == {}
        assert isinstance(config._defaults, dict)

    def test_defaults_defined(self, tmp_path):
        """Test default configuration values are defined."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        defaults = config._defaults

        # Check essential defaults exist
        assert "server_url" in defaults
        assert "api_key" in defaults
        assert "device_id" in defaults
        assert "auto_connect" in defaults
        assert "reconnect_interval" in defaults
        assert "log_level" in defaults

    def test_defaults_values(self, tmp_path):
        """Test default configuration values."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        assert config._defaults["server_url"] == "http://localhost:8080"
        assert config._defaults["api_key"] == ""
        assert config._defaults["device_id"] is None
        assert config._defaults["auto_connect"] is True
        assert config._defaults["reconnect_interval"] == 5000
        assert config._defaults["log_level"] == "INFO"


class TestConfigLoad:
    """Test cases for load() method."""

    def test_load_nonexistent_file_creates_defaults(self, tmp_path):
        """Test loading nonexistent file creates default config."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        result = config.load()

        # Should return defaults
        assert result == config._defaults
        assert config._config == config._defaults

        # Should create the file
        assert config_path.exists()

    def test_load_existing_file(self, tmp_path):
        """Test loading existing config file."""
        config_path = tmp_path / "config.json"

        # Create config file
        test_config = {
            "server_url": "http://test.com",
            "api_key": "test-key-123",
            "custom_value": "custom"
        }
        config_path.write_text(json.dumps(test_config))

        config = ConfigManager(config_path)
        result = config.load()

        assert result == test_config
        assert config._config == test_config
        assert config._config["server_url"] == "http://test.com"
        assert config._config["api_key"] == "test-key-123"
        assert config._config["custom_value"] == "custom"

    def test_load_empty_json(self, tmp_path):
        """Test loading empty JSON file."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        config = ConfigManager(config_path)
        result = config.load()

        assert result == {}
        assert config._config == {}

    def test_load_with_unicode(self, tmp_path):
        """Test loading config with unicode characters."""
        config_path = tmp_path / "config.json"

        test_config = {
            "name": "Тест",
            "emoji": "🚀",
            "chinese": "测试"
        }
        config_path.write_text(json.dumps(test_config, ensure_ascii=False))

        config = ConfigManager(config_path)
        result = config.load()

        assert result["name"] == "Тест"
        assert result["emoji"] == "🚀"
        assert result["chinese"] == "测试"


class TestConfigSave:
    """Test cases for save() method."""

    def test_save_creates_file(self, tmp_path):
        """Test save() creates config file."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        config._config = {"test": "value"}
        config.save()

        assert config_path.exists()

        # Verify content
        saved_data = json.loads(config_path.read_text())
        assert saved_data == {"test": "value"}

    def test_save_creates_parent_directory(self, tmp_path):
        """Test save() creates parent directory if needed."""
        config_path = tmp_path / "subdir" / "config.json"
        config = ConfigManager(config_path)

        config._config = {"test": "value"}
        config.save()

        assert config_path.parent.exists()
        assert config_path.exists()

    def test_save_overwrites_existing(self, tmp_path):
        """Test save() overwrites existing file."""
        config_path = tmp_path / "config.json"
        config_path.write_text('{"old": "data"}')

        config = ConfigManager(config_path)
        config._config = {"new": "data"}
        config.save()

        saved_data = json.loads(config_path.read_text())
        assert saved_data == {"new": "data"}
        assert "old" not in saved_data

    def test_save_preserves_unicode(self, tmp_path):
        """Test save() preserves unicode characters."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        config._config = {
            "russian": "Привет",
            "emoji": "🎉",
            "chinese": "你好"
        }
        config.save()

        saved_data = json.loads(config_path.read_text())
        assert saved_data["russian"] == "Привет"
        assert saved_data["emoji"] == "🎉"
        assert saved_data["chinese"] == "你好"

    def test_save_formatted_json(self, tmp_path):
        """Test save() creates formatted JSON."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        config._config = {"a": 1, "b": {"nested": 2}}
        config.save()

        # Check formatting (should have newlines)
        content = config_path.read_text()
        assert "\n" in content
        assert "  " in content  # Indentation


class TestConfigGetSet:
    """Test cases for get() and set() methods."""

    def test_get_existing_key(self, tmp_path):
        """Test get() with existing key."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"test_key": "test_value"}

        result = config.get("test_key")
        assert result == "test_value"

    def test_get_nonexistent_key_returns_none(self, tmp_path):
        """Test get() with nonexistent key returns None."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        result = config.get("nonexistent")
        assert result is None

    def test_get_with_custom_default(self, tmp_path):
        """Test get() with custom default value."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        result = config.get("nonexistent", "custom_default")
        assert result == "custom_default"

    def test_get_falls_back_to_defaults(self, tmp_path):
        """Test get() falls back to _defaults if key not in config."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        # Should use default from _defaults
        result = config.get("server_url")
        assert result == "http://localhost:8080"

    def test_set_new_key(self, tmp_path):
        """Test set() with new key."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        config.set("new_key", "new_value")

        assert config._config["new_key"] == "new_value"

    def test_set_overwrites_existing(self, tmp_path):
        """Test set() overwrites existing key."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"key": "old_value"}

        config.set("key", "new_value")

        assert config._config["key"] == "new_value"

    def test_set_different_types(self, tmp_path):
        """Test set() with different value types."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        config.set("string", "value")
        config.set("number", 123)
        config.set("boolean", True)
        config.set("list", [1, 2, 3])
        config.set("dict", {"nested": "value"})
        config.set("none", None)

        assert config._config["string"] == "value"
        assert config._config["number"] == 123
        assert config._config["boolean"] is True
        assert config._config["list"] == [1, 2, 3]
        assert config._config["dict"] == {"nested": "value"}
        assert config._config["none"] is None


class TestConfigUpdate:
    """Test cases for update() method."""

    def test_update_empty_config(self, tmp_path):
        """Test update() on empty config."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        config.update({"key1": "value1", "key2": "value2"})

        assert config._config["key1"] == "value1"
        assert config._config["key2"] == "value2"

    def test_update_merges_with_existing(self, tmp_path):
        """Test update() merges with existing config."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"existing": "value"}

        config.update({"new": "data"})

        assert config._config["existing"] == "value"
        assert config._config["new"] == "data"

    def test_update_overwrites_keys(self, tmp_path):
        """Test update() overwrites existing keys."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"key": "old"}

        config.update({"key": "new"})

        assert config._config["key"] == "new"


class TestConfigProperties:
    """Test cases for property accessors."""

    def test_server_url_property(self, tmp_path):
        """Test server_url property getter."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"server_url": "http://example.com"}

        assert config.server_url == "http://example.com"

    def test_server_url_default(self, tmp_path):
        """Test server_url returns default when not set."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        # Should return empty string (property override)
        assert config.server_url == ""

    def test_api_key_property(self, tmp_path):
        """Test api_key property getter."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"api_key": "secret-key"}

        assert config.api_key == "secret-key"

    def test_api_key_default(self, tmp_path):
        """Test api_key returns default when not set."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        assert config.api_key == ""

    def test_device_id_property_getter(self, tmp_path):
        """Test device_id property getter."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {"device_id": "device-123"}

        assert config.device_id == "device-123"

    def test_device_id_property_setter(self, tmp_path):
        """Test device_id property setter."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        config.device_id = "new-device-456"

        assert config._config["device_id"] == "new-device-456"
        assert config.device_id == "new-device-456"

    def test_device_id_default_none(self, tmp_path):
        """Test device_id returns None when not set."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)
        config._config = {}

        assert config.device_id is None


class TestConfigIntegration:
    """Integration tests for ConfigManager."""

    def test_full_workflow(self, tmp_path):
        """Test full load -> modify -> save -> load workflow."""
        config_path = tmp_path / "config.json"

        # First instance: create and save
        config1 = ConfigManager(config_path)
        config1.load()
        config1.set("test_key", "test_value")
        config1.device_id = "device-abc"
        config1.save()

        # Second instance: load saved config
        config2 = ConfigManager(config_path)
        config2.load()

        assert config2.get("test_key") == "test_value"
        assert config2.device_id == "device-abc"

    def test_multiple_save_load_cycles(self, tmp_path):
        """Test multiple save/load cycles."""
        config_path = tmp_path / "config.json"
        config = ConfigManager(config_path)

        # Cycle 1
        config.load()
        config.set("counter", 1)
        config.save()

        # Cycle 2
        config.load()
        config.set("counter", 2)
        config.save()

        # Verify
        config.load()
        assert config.get("counter") == 2

    def test_concurrent_instances_same_file(self, tmp_path):
        """Test two ConfigManager instances for same file."""
        config_path = tmp_path / "config.json"

        config1 = ConfigManager(config_path)
        config2 = ConfigManager(config_path)

        # config1 saves data
        config1.load()
        config1.set("key", "value1")
        config1.save()

        # config2 loads and sees the data
        config2.load()
        assert config2.get("key") == "value1"

        # config2 modifies
        config2.set("key", "value2")
        config2.save()

        # config1 reloads and sees new data
        config1.load()
        assert config1.get("key") == "value2"
