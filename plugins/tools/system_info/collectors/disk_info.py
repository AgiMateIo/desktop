"""Disk information collector."""

from typing import Any

import psutil


def collect_disk_info() -> list[dict[str, Any]]:
    """Collect mounted disk partition information using psutil."""
    disks = []
    for partition in psutil.disk_partitions(all=False):
        entry: dict[str, Any] = {
            "device": partition.device,
            "mountpoint": partition.mountpoint,
            "fstype": partition.fstype,
            "totalBytes": None,
            "usedBytes": None,
            "freeBytes": None,
            "usagePercent": None,
        }
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            entry["totalBytes"] = usage.total
            entry["usedBytes"] = usage.used
            entry["freeBytes"] = usage.free
            entry["usagePercent"] = usage.percent
        except (PermissionError, OSError):
            pass
        disks.append(entry)
    return disks
