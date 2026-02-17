"""CPU information collector."""

import platform
from typing import Any

import psutil


def collect_cpu_info() -> dict[str, Any]:
    """Collect CPU information using psutil."""
    freq = psutil.cpu_freq()
    return {
        "model": platform.processor() or "unknown",
        "physicalCores": psutil.cpu_count(logical=False),
        "logicalCores": psutil.cpu_count(logical=True),
        "usagePercent": psutil.cpu_percent(interval=0.1),
        "frequencyMhz": round(freq.current, 1) if freq else None,
        "frequencyMaxMhz": round(freq.max, 1) if freq else None,
    }
