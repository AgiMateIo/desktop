"""Tests for core.device_info module."""

import pytest
import socket
import platform
from unittest.mock import MagicMock
from core.device_info import DeviceInfo


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager with device_id."""
    mock = MagicMock()
    mock.device_id = "test-device-uuid-1234"
    return mock


class TestDeviceInfo:
    """Test cases for DeviceInfo class."""

    def test_init(self, mock_config_manager):
        """Test DeviceInfo initialization."""
        device_info = DeviceInfo(mock_config_manager)
        assert device_info._config_manager is mock_config_manager

    def test_device_id_from_config(self, mock_config_manager):
        """Test device_id is read from config manager."""
        device_info = DeviceInfo(mock_config_manager)
        assert device_info.device_id == "test-device-uuid-1234"

    def test_device_id_delegates_to_config(self, mock_config_manager):
        """Test device_id always delegates to config manager."""
        device_info = DeviceInfo(mock_config_manager)

        # Change the config manager's device_id
        mock_config_manager.device_id = "new-device-id"
        assert device_info.device_id == "new-device-id"

    def test_multiple_accesses_consistent(self, mock_config_manager):
        """Test multiple device_id accesses return same value."""
        device_info = DeviceInfo(mock_config_manager)
        ids = [device_info.device_id for _ in range(5)]
        assert len(set(ids)) == 1


class TestGetPlatform:
    """Test cases for get_platform() static method."""

    def test_get_platform_darwin(self, monkeypatch):
        """Test get_platform() returns 'macos' for Darwin."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")

        result = DeviceInfo.get_platform()
        assert result == "macos"

    def test_get_platform_windows(self, monkeypatch):
        """Test get_platform() returns 'windows' for Windows."""
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        result = DeviceInfo.get_platform()
        assert result == "windows"

    def test_get_platform_linux(self, monkeypatch):
        """Test get_platform() returns 'linux' for Linux."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        # Mock file read to avoid Raspberry Pi detection
        def mock_open(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("builtins.open", mock_open)

        result = DeviceInfo.get_platform()
        assert result == "linux"

    def test_get_platform_raspberry(self, monkeypatch, tmp_path):
        """Test get_platform() returns 'raspberry' for Raspberry Pi."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        # Create mock device-tree file
        mock_device_tree = tmp_path / "model"
        mock_device_tree.write_text("Raspberry Pi 4 Model B")

        # Mock open to return our file
        original_open = open

        def mock_open(path, *args, **kwargs):
            if path == "/proc/device-tree/model":
                return original_open(str(mock_device_tree), *args, **kwargs)
            raise FileNotFoundError()

        monkeypatch.setattr("builtins.open", mock_open)

        result = DeviceInfo.get_platform()
        assert result == "raspberry"

    def test_get_platform_unknown(self, monkeypatch):
        """Test get_platform() returns system name for unknown platform."""
        monkeypatch.setattr(platform, "system", lambda: "FreeBSD")

        result = DeviceInfo.get_platform()
        assert result == "freebsd"

    def test_get_platform_case_insensitive(self, monkeypatch):
        """Test get_platform() converts to lowercase."""
        monkeypatch.setattr(platform, "system", lambda: "LINUX")

        def mock_open(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("builtins.open", mock_open)

        result = DeviceInfo.get_platform()
        assert result == "linux"


class TestGetHostname:
    """Test cases for get_hostname() static method."""

    def test_get_hostname(self, monkeypatch):
        """Test get_hostname() returns socket.gethostname()."""
        monkeypatch.setattr(socket, "gethostname", lambda: "test-hostname")

        result = DeviceInfo.get_hostname()
        assert result == "test-hostname"

    def test_get_hostname_real(self):
        """Test get_hostname() returns actual hostname."""
        # Should not raise and should return a string
        hostname = DeviceInfo.get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0


class TestGetSystemInfo:
    """Test cases for get_system_info() static method."""

    def test_get_system_info_structure(self):
        """Test get_system_info() returns dict with expected keys."""
        info = DeviceInfo.get_system_info()

        # Check it's a dict
        assert isinstance(info, dict)

        # Check required keys
        required_keys = [
            "platform",
            "hostname",
            "system",
            "release",
            "version",
            "machine",
            "processor",
            "python_version"
        ]
        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_get_system_info_values(self, monkeypatch):
        """Test get_system_info() returns correct values."""
        # Mock platform functions
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.setattr(platform, "release", lambda: "5.10.0")
        monkeypatch.setattr(platform, "version", lambda: "#1 SMP")
        monkeypatch.setattr(platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(platform, "processor", lambda: "Intel")
        monkeypatch.setattr(platform, "python_version", lambda: "3.11.0")
        monkeypatch.setattr(socket, "gethostname", lambda: "test-host")

        # Mock file operations for Linux (not Raspberry Pi)
        def mock_open(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("builtins.open", mock_open)

        info = DeviceInfo.get_system_info()

        assert info["platform"] == "linux"
        assert info["hostname"] == "test-host"
        assert info["system"] == "Linux"
        assert info["release"] == "5.10.0"
        assert info["version"] == "#1 SMP"
        assert info["machine"] == "x86_64"
        assert info["processor"] == "Intel"
        assert info["python_version"] == "3.11.0"

    def test_get_system_info_types(self):
        """Test all values in get_system_info() are strings."""
        info = DeviceInfo.get_system_info()

        for key, value in info.items():
            assert isinstance(value, str), f"{key} is not a string: {type(value)}"
