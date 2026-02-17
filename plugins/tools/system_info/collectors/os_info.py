"""OS information collector."""

import logging
import platform
import socket
from typing import Any

logger = logging.getLogger(__name__)


def collect_os_info() -> dict[str, Any]:
    """Collect operating system information.

    Combines stdlib platform/socket data with PySide6 QSysInfo
    for richer OS details (pretty name, kernel info, machine IDs).
    """
    data: dict[str, Any] = {
        "name": platform.system(),
        "version": platform.version(),
        "release": platform.release(),
        "hostname": socket.gethostname(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }

    try:
        from PySide6.QtCore import QSysInfo

        data["prettyName"] = QSysInfo.prettyProductName()
        data["productType"] = QSysInfo.productType()
        data["productVersion"] = QSysInfo.productVersion()
        data["kernelType"] = QSysInfo.kernelType()
        data["kernelVersion"] = QSysInfo.kernelVersion()
        data["cpuArchitecture"] = QSysInfo.currentCpuArchitecture()
        data["buildAbi"] = QSysInfo.buildAbi()

        machine_id = QSysInfo.machineUniqueId()
        if machine_id:
            data["machineUniqueId"] = bytes(machine_id).decode("ascii", errors="replace")

        boot_id = QSysInfo.bootUniqueId()
        if boot_id:
            data["bootUniqueId"] = bytes(boot_id).decode("ascii", errors="replace")

    except Exception as e:
        logger.debug(f"QSysInfo unavailable: {e}")

    return data
