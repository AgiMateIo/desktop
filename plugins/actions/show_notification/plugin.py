"""Show Notification action plugin implementation."""

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from PySide6.QtWidgets import QSystemTrayIcon

from core.plugin_base import ActionPlugin
from core.action_types import ACTION_NOTIFICATION, ACTION_NOTIFICATION_MODAL
from core.constants import DEFAULT_NOTIFICATION_DURATION_MS

if TYPE_CHECKING:
    from ui.tray import TrayManager

logger = logging.getLogger(__name__)


class ShowNotificationAction(ActionPlugin):
    """Action plugin for showing system and modal notifications."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._tray_manager: "TrayManager | None" = None

    @property
    def name(self) -> str:
        return "Show Notification"

    def set_tray_manager(self, tray_manager: "TrayManager") -> None:
        """Set the tray manager for notifications."""
        self._tray_manager = tray_manager
        logger.info("Tray manager set for notifications")

    # Keep for backward compatibility
    def set_tray_icon(self, tray_icon: QSystemTrayIcon) -> None:
        """Deprecated: Use set_tray_manager instead."""
        pass

    def get_supported_actions(self) -> list[str]:
        return [ACTION_NOTIFICATION, ACTION_NOTIFICATION_MODAL]

    async def initialize(self) -> None:
        """Initialize the plugin."""
        logger.info("ShowNotificationAction initialized")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        logger.info("ShowNotificationAction shutdown")

    async def execute(self, action_type: str, parameters: dict[str, Any]) -> bool:
        """
        Execute a notification action.

        Parameters:
            title: Notification title
            message: Notification message
            duration: Duration in ms (for system notifications only)
            modal: If True, show modal dialog (alternative to NOTIFICATION_MODAL)
        """
        if action_type not in [ACTION_NOTIFICATION, ACTION_NOTIFICATION_MODAL]:
            return False

        if self._tray_manager is None:
            logger.error("Tray manager not set, cannot show notification")
            return False

        title = parameters.get("title", self.get_config("default_title", "Agimate"))
        message = parameters.get("message", "")
        duration = parameters.get("duration", self.get_config("default_duration", DEFAULT_NOTIFICATION_DURATION_MS))

        # Determine if modal
        is_modal = (
            action_type == ACTION_NOTIFICATION_MODAL or
            parameters.get("modal", False)
        )

        if not message:
            logger.warning("No message provided for notification")
            return False

        try:
            from ui.tray import NotificationType

            notification_type = NotificationType.MODAL if is_modal else NotificationType.SYSTEM

            result = self._tray_manager.show_message(
                title=title,
                message=message,
                duration=duration,
                notification_type=notification_type
            )

            logger.info(f"Showed {'modal' if is_modal else 'system'} notification: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
            return False
