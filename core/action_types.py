"""
Action and event type constants.

Defines all action types supported by the system and validation lists.
"""

# Event Types
EVENT_TYPE_DEVICE = "DEVICE_EVENT"

# Action Types
ACTION_NOTIFICATION = "desktop.action.notification.show"
ACTION_NOTIFICATION_MODAL = "desktop.action.notification.show_modal"
ACTION_TTS = "desktop.action.tts.speak"
ACTION_TTS_STOP = "desktop.action.tts.stop"

# Validation Lists
ALL_NOTIFICATION_ACTIONS = [ACTION_NOTIFICATION, ACTION_NOTIFICATION_MODAL]
ALL_TTS_ACTIONS = [ACTION_TTS, ACTION_TTS_STOP]
