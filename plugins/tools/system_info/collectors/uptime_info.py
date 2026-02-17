"""System uptime collector."""

from datetime import datetime, timezone
from typing import Any

import psutil


def collect_uptime_info() -> dict[str, Any]:
    """Collect system boot time and uptime using psutil."""
    boot_ts = psutil.boot_time()
    boot_dt = datetime.fromtimestamp(boot_ts, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    uptime_seconds = int((now - boot_dt).total_seconds())

    return {
        "bootTime": boot_dt.isoformat().replace("+00:00", "Z"),
        "uptimeSeconds": uptime_seconds,
    }
