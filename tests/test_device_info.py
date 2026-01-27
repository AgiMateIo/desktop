"""Tests for core.device_info module."""

import pytest
import socket
import platform
from pathlib import Path
from core.device_info import DeviceInfo


class TestDeviceInfo:
    """Test cases for DeviceInfo class."""

    def test_init(self, tmp_path):
        """Test DeviceInfo initialization."""
        device_info = DeviceInfo(tmp_path)

        assert device_info.data_dir == tmp_path
        assert device_info._device_id_file == tmp_path / ".device_id"
        assert device_info._device_id is None  # Not loaded yet

    def test_device_id_generation(self, tmp_path):
        """Test device_id generation on first access."""
        device_info = DeviceInfo(tmp_path)

        # First access should generate new ID
        device_id = device_info.device_id

        # Check UUID format (36 chars with 4 hyphens)
        assert len(device_id) == 36
        assert device_id.count("-") == 4

        # Check it's persisted to file
        device_id_file = tmp_path / ".device_id"
        assert device_id_file.exists()
        assert device_id_file.read_text().strip() == device_id

    def test_device_id_persistence(self, tmp_path):
        """Test device_id is loaded from file if exists."""
        # Create existing device ID file
        existing_id = "existing-uuid-1234-5678-abcd"
        device_id_file = tmp_path / ".device_id"
        device_id_file.write_text(existing_id)

        # DeviceInfo should load existing ID
        device_info = DeviceInfo(tmp_path)
        assert device_info.device_id == existing_id

        # Should not create a new ID
        assert device_id_file.read_text().strip() == existing_id

    def test_device_id_cached(self, tmp_path):
        """Test device_id is cached after first access."""
        device_info = DeviceInfo(tmp_path)

        # First access
        id1 = device_info.device_id

        # Second access should return same ID (cached)
        id2 = device_info.device_id
        assert id1 == id2

        # Verify _device_id is set
        assert device_info._device_id == id1

    def test_device_id_with_whitespace(self, tmp_path):
        """Test device_id loaded correctly even with whitespace."""
        # Write ID with trailing/leading whitespace
        existing_id = "test-uuid-with-whitespace"
        device_id_file = tmp_path / ".device_id"
        device_id_file.write_text(f"  {existing_id}  \n")

        device_info = DeviceInfo(tmp_path)
        # Should strip whitespace
        assert device_info.device_id == existing_id


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


class TestDeviceInfoIntegration:
    """Integration tests for DeviceInfo."""

    def test_full_workflow(self, tmp_path):
        """Test full workflow: create, save, load."""
        # Create new DeviceInfo
        device_info1 = DeviceInfo(tmp_path)
        id1 = device_info1.device_id

        # Create another instance (should load same ID)
        device_info2 = DeviceInfo(tmp_path)
        id2 = device_info2.device_id

        assert id1 == id2

    def test_multiple_accesses(self, tmp_path):
        """Test multiple device_id accesses return same value."""
        device_info = DeviceInfo(tmp_path)

        ids = [device_info.device_id for _ in range(5)]

        # All IDs should be identical
        assert len(set(ids)) == 1

    def test_data_dir_created(self, tmp_path):
        """Test data_dir is created if it doesn't exist."""
        non_existent_dir = tmp_path / "new_dir"
        assert not non_existent_dir.exists()

        device_info = DeviceInfo(non_existent_dir)
        _ = device_info.device_id

        # Directory should be created
        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()
