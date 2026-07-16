"""
Tool and event type constants.

Defines all tool types supported by the system and validation lists.

Names are bare snake_case local identifiers (no prefixes) per the app-connector
contract: the backend derives a per-instance namespace (e.g. "app_desktop")
and shows the agent "app_desktop.tts_speak", while tool calls arrive with the
bare name declared at link time.
"""

# Event Types
EVENT_TYPE_DEVICE = "DEVICE_EVENT"

# Tool Types
TOOL_NOTIFICATION = "notification_show"
TOOL_NOTIFICATION_MODAL = "notification_show_modal"
TOOL_TTS = "tts_speak"
TOOL_TTS_STOP = "tts_stop"
TOOL_FILES_LIST = "files_list"
TOOL_SCREENSHOT_FULLSCREEN = "screenshot_fullscreen"
TOOL_SCREENSHOT_WINDOW = "screenshot_window"
TOOL_SCREENSHOT_REGION = "screenshot_region"
TOOL_WINDOWS_LIST = "windows_list"
TOOL_APPS_LIST = "apps_list"
TOOL_SYSINFO_SNAPSHOT = "sysinfo_snapshot"
TOOL_SYSINFO_SCREENS = "sysinfo_screens"

# Validation Lists
ALL_NOTIFICATION_TOOLS = [TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL]
ALL_TTS_TOOLS = [TOOL_TTS, TOOL_TTS_STOP]
ALL_FILES_TOOLS = [TOOL_FILES_LIST]
ALL_SCREENSHOT_TOOLS = [TOOL_SCREENSHOT_FULLSCREEN, TOOL_SCREENSHOT_WINDOW, TOOL_SCREENSHOT_REGION]
ALL_WINDOW_LIST_TOOLS = [TOOL_WINDOWS_LIST, TOOL_APPS_LIST]
ALL_SYSINFO_TOOLS = [TOOL_SYSINFO_SNAPSHOT, TOOL_SYSINFO_SCREENS]
