"""Tests for core.paths module."""

import pytest
import sys
from pathlib import Path
from core.paths import get_app_dir, get_data_dir, get_plugins_dir, get_config_path, is_bundled


class TestGetAppDir:
    """Test cases for get_app_dir()."""

    def test_script_mode(self, monkeypatch):
        """Test get_app_dir() in script mode (not bundled)."""
        # Ensure we're not frozen
        monkeypatch.delattr("sys.frozen", raising=False)

        app_dir = get_app_dir()

        # In script mode, should return parent of core/ directory
        assert app_dir.exists()
        assert (app_dir / "core").exists()
        assert (app_dir / "main.py").exists()

    def test_bundled_mode(self, monkeypatch):
        """Test get_app_dir() in bundled mode (frozen)."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/tmp/test_meipass", raising=False)

        app_dir = get_app_dir()

        assert str(app_dir) == "/tmp/test_meipass"


class TestGetDataDir:
    """Test cases for get_data_dir()."""

    def test_script_mode(self, monkeypatch):
        """Test get_data_dir() in script mode returns project root."""
        monkeypatch.delattr("sys.frozen", raising=False)

        data_dir = get_data_dir()

        # In script mode, should be same as project root
        assert data_dir.exists()
        assert (data_dir / "core").exists()

    def test_bundled_mode_macos(self, monkeypatch):
        """Test get_data_dir() in bundled mode on macOS."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr("sys.platform", "darwin")

        data_dir = get_data_dir()

        assert "Library/Application Support/AgimateDesktop" in str(data_dir)

    def test_bundled_mode_windows(self, monkeypatch):
        """Test get_data_dir() in bundled mode on Windows."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr("sys.platform", "win32")

        data_dir = get_data_dir()

        assert "AppData" in str(data_dir) or "Local" in str(data_dir)
        assert "AgimateDesktop" in str(data_dir)

    def test_bundled_mode_linux(self, monkeypatch):
        """Test get_data_dir() in bundled mode on Linux."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr("sys.platform", "linux")

        data_dir = get_data_dir()

        assert ".config/agimatedesktop" in str(data_dir)

    def test_data_dir_created(self, monkeypatch, tmp_path):
        """Test that get_data_dir() creates directory if it doesn't exist."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr("sys.platform", "linux")

        # Mock Path.home() to return tmp_path
        def mock_home():
            return tmp_path

        monkeypatch.setattr(Path, "home", mock_home)

        data_dir = get_data_dir()

        # Directory should be created
        assert data_dir.exists()
        assert data_dir.is_dir()


class TestGetPluginsDir:
    """Test cases for get_plugins_dir()."""

    def test_plugins_dir_path(self, monkeypatch):
        """Test get_plugins_dir() returns correct path."""
        monkeypatch.delattr("sys.frozen", raising=False)

        plugins_dir = get_plugins_dir()

        assert plugins_dir.name == "plugins"
        # Should be app_dir / plugins
        assert plugins_dir.parent.name == "agimate-desktop"

    def test_plugins_dir_in_bundled_mode(self, monkeypatch):
        """Test get_plugins_dir() in bundled mode."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/tmp/test_bundle", raising=False)

        plugins_dir = get_plugins_dir()

        assert str(plugins_dir) == "/tmp/test_bundle/plugins"


class TestGetConfigPath:
    """Test cases for get_config_path()."""

    def test_config_path(self, monkeypatch):
        """Test get_config_path() returns data_dir/config.json."""
        monkeypatch.delattr("sys.frozen", raising=False)

        config_path = get_config_path()

        assert config_path.name == "config.json"
        # Should be in data directory
        assert str(config_path).endswith("config.json")


class TestIsBundled:
    """Test cases for is_bundled()."""

    def test_not_bundled(self, monkeypatch):
        """Test is_bundled() returns False when not frozen."""
        monkeypatch.delattr("sys.frozen", raising=False)

        assert is_bundled() is False

    def test_bundled(self, monkeypatch):
        """Test is_bundled() returns True when frozen."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)

        assert is_bundled() is True

    def test_bundled_false_value(self, monkeypatch):
        """Test is_bundled() with frozen=False."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)

        assert is_bundled() is False


class TestCrossPlatformPaths:
    """Test path utilities across different platforms."""

    @pytest.mark.parametrize("platform,expected_component", [
        ("darwin", "Library"),
        ("win32", "AppData"),
        ("linux", ".config"),
    ])
    def test_data_dir_platform_specific(self, monkeypatch, platform, expected_component):
        """Test data directory is platform-specific in bundled mode."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr("sys.platform", platform)

        data_dir = get_data_dir()

        assert expected_component in str(data_dir)
        assert "AgimateDesktop" in str(data_dir) or "agimatedesktop" in str(data_dir)
