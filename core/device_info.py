"""Device information utilities."""

import platform
import socket

from core.protocols import IConfigManager


class DeviceInfo:
    """Provides information about the current device."""

    def __init__(self, config_manager: IConfigManager):
        self._config_manager = config_manager

    @property
    def device_id(self) -> str:
        """Get the device ID from configuration."""
        return self._config_manager.device_id

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
