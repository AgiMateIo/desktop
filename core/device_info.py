"""Device information utilities."""

import platform
import socket
import uuid
from pathlib import Path


class DeviceInfo:
    """Provides information about the current device."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._device_id_file = data_dir / ".device_id"
        self._device_id: str | None = None

    @property
    def device_id(self) -> str:
        """Get or generate a unique device ID."""
        if self._device_id is None:
            self._device_id = self._load_or_generate_device_id()
        return self._device_id

    def _load_or_generate_device_id(self) -> str:
        """Load device ID from file or generate a new one."""
        if self._device_id_file.exists():
            return self._device_id_file.read_text().strip()

        device_id = str(uuid.uuid4())
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._device_id_file.write_text(device_id)
        return device_id

    @staticmethod
    def get_platform() -> str:
        """Get the current platform name."""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        elif system == "linux":
            # Check for Raspberry Pi
            try:
                with open("/proc/device-tree/model", "r") as f:
                    if "raspberry" in f.read().lower():
                        return "raspberry"
            except (FileNotFoundError, PermissionError):
                pass
            return "linux"
        return system

    @staticmethod
    def get_hostname() -> str:
        """Get the hostname of the current device."""
        return socket.gethostname()

    @staticmethod
    def get_system_info() -> dict:
        """Get detailed system information."""
        return {
            "platform": DeviceInfo.get_platform(),
            "hostname": DeviceInfo.get_hostname(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
