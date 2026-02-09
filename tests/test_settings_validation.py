"""Tests for settings validation."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.device_info import DeviceInfo


@pytest.fixture
def config_manager(tmp_path):
    """Create a test config manager."""
    config_path = tmp_path / "config.json"
    return ConfigManager(config_path)


@pytest.fixture
def plugin_manager(tmp_path):
    """Create a mock plugin manager."""
    mock = MagicMock(spec=PluginManager)
    mock.triggers = {}
    mock.actions = {}
    return mock


@pytest.fixture
def device_info(config_manager):
    """Create a test device info."""
    config_manager.load()
    return DeviceInfo(config_manager)


@pytest.fixture
def settings_window(config_manager, plugin_manager, device_info):
    """Create settings window instance."""
    # Import here to avoid Qt initialization issues in tests
    try:
        from PySide6.QtWidgets import QApplication
        from ui.settings import SettingsWindow

        # Create QApplication if it doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        window = SettingsWindow(config_manager, plugin_manager, device_info)
        yield window

        # Clean up
        if window:
            window.deleteLater()
    except ImportError:
        pytest.skip("PySide6 not available")
    except Exception as e:
        pytest.skip(f"Could not create Qt window: {e}")


class TestServerUrlValidation:
    """Tests for server URL validation."""

    def test_valid_http_url(self, settings_window):
        valid, error = settings_window._validate_server_url("http://localhost:8080")
        assert valid is True
        assert error == ""

    def test_valid_https_url(self, settings_window):
        valid, error = settings_window._validate_server_url("https://example.com")
        assert valid is True
        assert error == ""

    def test_valid_url_with_path(self, settings_window):
        valid, error = settings_window._validate_server_url("https://example.com/api")
        assert valid is True
        assert error == ""

    def test_valid_url_with_port(self, settings_window):
        valid, error = settings_window._validate_server_url("http://localhost:3000")
        assert valid is True
        assert error == ""

    def test_empty_url_invalid(self, settings_window):
        valid, error = settings_window._validate_server_url("")
        assert valid is False
        assert "cannot be empty" in error.lower()

    def test_whitespace_url_invalid(self, settings_window):
        valid, error = settings_window._validate_server_url("   ")
        assert valid is False
        assert "cannot be empty" in error.lower()

    def test_url_without_scheme_invalid(self, settings_window):
        valid, error = settings_window._validate_server_url("example.com")
        assert valid is False
        assert "http://" in error or "https://" in error

    def test_url_with_invalid_scheme(self, settings_window):
        valid, error = settings_window._validate_server_url("ftp://example.com")
        assert valid is False
        assert "invalid" in error.lower() or "scheme" in error.lower()

    def test_url_without_hostname(self, settings_window):
        valid, error = settings_window._validate_server_url("http://")
        assert valid is False
        assert "hostname" in error.lower()


class TestDeviceKeyValidation:
    """Tests for device key validation."""

    def test_valid_device_key(self, settings_window):
        valid, error = settings_window._validate_device_key("1234567890abcdef")
        assert valid is True
        assert error == ""

    def test_long_device_key_valid(self, settings_window):
        valid, error = settings_window._validate_device_key("a" * 50)
        assert valid is True
        assert error == ""

    def test_empty_device_key_valid(self, settings_window):
        # Empty device key is allowed
        valid, error = settings_window._validate_device_key("")
        assert valid is True
        assert error == ""

    def test_short_device_key_invalid(self, settings_window):
        valid, error = settings_window._validate_device_key("short")
        assert valid is False
        assert "10 characters" in error

    def test_exactly_10_chars_valid(self, settings_window):
        valid, error = settings_window._validate_device_key("1234567890")
        assert valid is True
        assert error == ""

    def test_9_chars_invalid(self, settings_window):
        valid, error = settings_window._validate_device_key("123456789")
        assert valid is False
        assert "10 characters" in error

    def test_whitespace_only_valid(self, settings_window):
        # Whitespace-only is treated as empty after strip
        valid, error = settings_window._validate_device_key("   ")
        assert valid is True
        assert error == ""


class TestSaveSettingsValidation:
    """Tests for settings save with validation."""

    def test_save_with_valid_settings(self, settings_window):
        settings_window.server_url_edit.setText("http://localhost:8080")
        settings_window.device_key_edit.setText("valid_device_key_12345")

        # Mock message boxes to avoid UI popup
        with patch("PySide6.QtWidgets.QMessageBox.information"):
            settings_window._save_settings()

        # Should save successfully
        assert settings_window.config_manager.get("server_url") == "http://localhost:8080"
        assert settings_window.config_manager.get("device_key") == "valid_device_key_12345"

    def test_save_with_invalid_url_shows_error(self, settings_window):
        settings_window.server_url_edit.setText("")
        settings_window.device_key_edit.setText("valid_device_key_12345")

        # Mock message box to avoid UI popup
        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
            settings_window._save_settings()

        # Should show validation error
        mock_warning.assert_called_once()
        call_args = mock_warning.call_args
        assert "Validation Error" in call_args[0][1]
        assert "cannot be empty" in call_args[0][2].lower()

    def test_save_with_invalid_device_key_shows_error(self, settings_window):
        settings_window.server_url_edit.setText("http://localhost:8080")
        settings_window.device_key_edit.setText("short")

        # Mock message box to avoid UI popup
        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
            settings_window._save_settings()

        # Should show validation error
        mock_warning.assert_called_once()
        call_args = mock_warning.call_args
        assert "Validation Error" in call_args[0][1]
        assert "10 characters" in call_args[0][2]

    def test_save_trims_whitespace_from_url(self, settings_window):
        settings_window.server_url_edit.setText("  http://localhost:8080  ")
        settings_window.device_key_edit.setText("valid_device_key_12345")

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            settings_window._save_settings()

        # URL should be trimmed
        assert settings_window.config_manager.get("server_url") == "http://localhost:8080"

    def test_save_with_empty_device_key_allowed(self, settings_window):
        settings_window.server_url_edit.setText("http://localhost:8080")
        settings_window.device_key_edit.setText("")

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            settings_window._save_settings()

        # Empty device key is allowed
        assert settings_window.config_manager.get("server_url") == "http://localhost:8080"
        assert settings_window.config_manager.get("device_key") == ""
