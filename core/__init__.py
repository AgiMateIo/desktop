"""Core module for Agimate Desktop."""

from .plugin_base import (
    TrayMenuItem,
    PluginEvent,
    PluginBase,
    TriggerPlugin,
    ToolPlugin,
)
from .plugin_manager import PluginManager
from .config_manager import ConfigManager
from .device_info import DeviceInfo
from .models import TriggerPayload, ToolTask
from .server_client import ServerClient

__all__ = [
    "TrayMenuItem",
    "PluginEvent",
    "PluginBase",
    "TriggerPlugin",
    "ToolPlugin",
    "PluginManager",
    "ConfigManager",
    "DeviceInfo",
    "TriggerPayload",
    "ToolTask",
    "ServerClient",
]
