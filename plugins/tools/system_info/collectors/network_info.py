"""Network information collector."""

import socket
from typing import Any

import psutil


def collect_network_info() -> list[dict[str, Any]]:
    """Collect network interface IP addresses using psutil."""
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        ipv4 = [
            {"address": a.address, "netmask": a.netmask, "broadcast": a.broadcast}
            for a in addr_list
            if a.family == socket.AF_INET
        ]
        ipv6 = [
            {"address": a.address.split("%")[0]}
            for a in addr_list
            if a.family == socket.AF_INET6
        ]
        iface_stats = stats.get(iface_name)
        interfaces.append({
            "name": iface_name,
            "isUp": iface_stats.isup if iface_stats else None,
            "ipv4": ipv4,
            "ipv6": ipv6,
        })
    return interfaces
