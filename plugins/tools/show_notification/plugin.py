"""Show Notification tool plugin implementation."""

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

from PySide6.QtWidgets import QSystemTrayIcon

from core.plugin_base import ToolPlugin
from core.tool_types import TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL
from core.models import ToolResult
from core.constants import DEFAULT_NOTIFICATION_DURATION_MS

if TYPE_CHECKING:
    from ui.tray import TrayManager

logger = logging.getLogger(__name__)


class ShowNotificationTool(ToolPlugin):
    """Tool plugin for showing system and modal notifications."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._tray_manager: "TrayManager | None" = None

    @property
    def name(self) -> str:
        return "Show Notification"

    @property
    def description(self) -> str:
        return "Shows system or modal notifications on the desktop"

    def set_tray_manager(self, tray_manager: "TrayManager") -> None:
        """Set the tray manager for notifications."""
        self._tray_manager = tray_manager
        logger.info("Tray manager set for notifications")

    # Keep for backward compatibility
    def set_tray_icon(self, tray_icon: QSystemTrayIcon) -> None:
        """Deprecated: Use set_tray_manager instead."""
        pass

    def get_supported_tools(self) -> list[str]:
        return [TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return notification tool capabilities."""
        params = ["title", "message", "duration", "modal"]
        return {
            TOOL_NOTIFICATION: {
                "params": params,
                "description": "Show a system notification",
            },
            TOOL_NOTIFICATION_MODAL: {
                "params": params,
                "description": "Show a modal notification dialog",
            },
        }

    async def initialize(self) -> None:
        """Initialize the plugin."""
        logger.info("ShowNotificationTool initialized")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        logger.info("ShowNotificationTool shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        """
        Execute a notification tool.

        Parameters:
            title: Notification title
            message: Notification message
            duration: Duration in ms (for system notifications only)
            modal: If True, show modal dialog (alternative to NOTIFICATION_MODAL)
        """
        if tool_type not in [TOOL_NOTIFICATION, TOOL_NOTIFICATION_MODAL]:
            return ToolResult(success=False, error=f"Unsupported tool: {tool_type}")

        if self._tray_manager is None:
            logger.error("Tray manager not set, cannot show notification")
            return ToolResult(success=False, error="Tray manager not set")

        title = parameters.get("title", self.get_config("default_title", "Agimate"))
        message = parameters.get("message", "")
        duration = parameters.get("duration", self.get_config("default_duration", DEFAULT_NOTIFICATION_DURATION_MS))

        # Determine if modal
        is_modal = (
            tool_type == TOOL_NOTIFICATION_MODAL or
            parameters.get("modal", False)
        )

        if not message:
            logger.warning("No message provided for notification")
            return ToolResult(success=False, error="No message provided")

        try:
            from ui.tray import NotificationType

            notification_type = NotificationType.MODAL if is_modal else NotificationType.SYSTEM

            self._tray_manager.show_message(
                title=title,
                message=message,
                duration=duration,
                notification_type=notification_type
            )

            logger.info(f"Showed {'modal' if is_modal else 'system'} notification: {title}")
            return ToolResult(success=True)
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
            return ToolResult(success=False, error=str(e))
