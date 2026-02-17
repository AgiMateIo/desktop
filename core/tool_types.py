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

# Validation Lists
ALL_NOTIFICATION_TOOLS = [TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL]
ALL_TTS_TOOLS = [TOOL_TTS, TOOL_TTS_STOP]
ALL_FILES_TOOLS = [TOOL_FILES_LIST]
