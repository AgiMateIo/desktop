"""OS information collector."""

import platform
import socket
from typing import Any


def collect_os_info() -> dict[str, Any]:
    """Collect operating system information."""
    return {
        "name": platform.system(),
        "version": platform.version(),
        "release": platform.release(),
        "hostname": socket.gethostname(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }
