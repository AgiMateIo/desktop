"""Memory (RAM) information collector."""

from typing import Any

import psutil


def collect_memory_info() -> dict[str, Any]:
    """Collect RAM usage using psutil."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "totalBytes": mem.total,
        "availableBytes": mem.available,
        "usedBytes": mem.used,
        "usagePercent": mem.percent,
        "swap": {
            "totalBytes": swap.total,
            "usedBytes": swap.used,
            "freeBytes": swap.free,
            "usagePercent": swap.percent,
        },
    }
