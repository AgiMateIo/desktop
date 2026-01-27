"""
Platform-specific command constants.

Defines commands and flags for macOS, Linux, and Windows platforms.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MacOSCommands:
    """macOS-specific commands."""
    TERMINAL_NOTIFIER = "terminal-notifier"
    OSASCRIPT = "osascript"
    SAY = "say"
    SAY_VOICE_FLAG = "-v"
    SAY_RATE_FLAG = "-r"


@dataclass(frozen=True)
class LinuxCommands:
    """Linux-specific commands."""
    NOTIFY_SEND = "notify-send"
    ESPEAK = "espeak"
    SPD_SAY = "spd-say"


@dataclass(frozen=True)
class WindowsCommands:
    """Windows-specific commands."""
    POWERSHELL = "powershell"
    POWERSHELL_COMMAND_FLAG = "-Command"
