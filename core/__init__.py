"""Core module for System Agent."""

from .plugin_base import (
    TrayMenuItem,
    PluginEvent,
    PluginBase,
    TriggerPlugin,
    ActionPlugin,
)
from .plugin_manager import PluginManager
from .config_manager import ConfigManager
from .device_info import DeviceInfo
from .models import TriggerPayload, ActionTask
from .server_client import ServerClient

__all__ = [
    "TrayMenuItem",
    "PluginEvent",
    "PluginBase",
    "TriggerPlugin",
    "ActionPlugin",
    "PluginManager",
    "ConfigManager",
    "DeviceInfo",
    "TriggerPayload",
    "ActionTask",
    "ServerClient",
]
