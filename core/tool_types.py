"""
Tool and event type constants.

Defines all tool types supported by the system and validation lists.
"""

# Event Types
EVENT_TYPE_DEVICE = "DEVICE_EVENT"

# Tool Types
TOOL_NOTIFICATION = "desktop.tool.notification.show"
TOOL_NOTIFICATION_MODAL = "desktop.tool.notification.show_modal"
TOOL_TTS = "desktop.tool.tts.speak"
TOOL_TTS_STOP = "desktop.tool.tts.stop"
TOOL_FILES_LIST = "desktop.tool.files.list"
TOOL_SCREENSHOT_FULLSCREEN = "desktop.tool.screenshot.fullscreen"
TOOL_SCREENSHOT_WINDOW = "desktop.tool.screenshot.window"
TOOL_SCREENSHOT_REGION = "desktop.tool.screenshot.region"
TOOL_WINDOWS_LIST = "desktop.tool.windows.list"
TOOL_APPS_LIST = "desktop.tool.apps.list"
TOOL_SYSINFO_SNAPSHOT = "desktop.tool.sysinfo.snapshot"
TOOL_SYSINFO_SCREENS = "desktop.tool.sysinfo.screens"

# Validation Lists
ALL_NOTIFICATION_TOOLS = [TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL]
ALL_TTS_TOOLS = [TOOL_TTS, TOOL_TTS_STOP]
ALL_FILES_TOOLS = [TOOL_FILES_LIST]
ALL_SCREENSHOT_TOOLS = [TOOL_SCREENSHOT_FULLSCREEN, TOOL_SCREENSHOT_WINDOW, TOOL_SCREENSHOT_REGION]
ALL_WINDOW_LIST_TOOLS = [TOOL_WINDOWS_LIST, TOOL_APPS_LIST]
ALL_SYSINFO_TOOLS = [TOOL_SYSINFO_SNAPSHOT, TOOL_SYSINFO_SCREENS]
