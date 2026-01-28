"""System tray manager for the application."""

import logging
import platform
import subprocess
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from enum import Enum

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QMessageBox
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Signal, QObject

from core.constants import (
    DEFAULT_NOTIFICATION_DURATION_MS,
    PLATFORM_MACOS,
    PLATFORM_LINUX,
    PLATFORM_WINDOWS,
)
from core.platform_commands import MacOSCommands, LinuxCommands, WindowsCommands

if TYPE_CHECKING:
    from core.event_bus import EventBus, Topics

# Subprocess timeout in seconds (to prevent hanging)
SUBPROCESS_TIMEOUT = 5.0


class NotificationType(Enum):
    """Type of notification to show."""
    SYSTEM = "system"  # Native system notification (non-blocking)
    MODAL = "modal"    # Modal dialog (blocking, requires user action)


class ConnectionStatus(Enum):
    """Connection status for tray icon."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

from core.plugin_base import TrayMenuItem

logger = logging.getLogger(__name__)


class TraySignals(QObject):
    """Signals for tray events."""

    settings_requested = Signal()
    quit_requested = Signal()


class TrayManager:
    """Manages the system tray icon and menu."""

    def __init__(self, app: QApplication, assets_dir: Path, event_bus: "EventBus | None" = None):
        """Initialize tray manager.

        Args:
            app: Qt application instance
            assets_dir: Directory containing assets (icons, etc.)
            event_bus: Optional EventBus for decoupled communication.
                      If provided, UI events will be published to the bus.
                      If None, only Qt signals are used (backward compatibility).
        """
        self.app = app
        self.assets_dir = assets_dir
        self.signals = TraySignals()
        self._event_bus = event_bus

        self._tray_icon = QSystemTrayIcon()
        self._menu = QMenu()
        self._plugin_items: list[TrayMenuItem] = []
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._connect_action: QAction | None = None

        self._setup_icon()
        self._build_menu()

        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.setToolTip("System Agent")

        # If EventBus is provided, publish events when signals are emitted
        if self._event_bus:
            self._setup_event_bus_integration()

    def _setup_icon(self) -> None:
        """Set up the tray icon."""
        icon_path = self.assets_dir / "icon.png"
        if icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            # Use a default icon if custom icon not found
            self._tray_icon.setIcon(self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_ComputerIcon
            ))

    def _build_menu(self) -> None:
        """Build the tray menu."""
        self._menu.clear()

        # Plugin items
        for item in self._plugin_items:
            self._add_menu_item(self._menu, item)

        if self._plugin_items:
            self._menu.addSeparator()

        # Connect/Disconnect action
        self._connect_action = QAction(self._get_connect_button_text(), self._menu)
        self._connect_action.setEnabled(self._connection_status != ConnectionStatus.CONNECTING)
        self._connect_action.triggered.connect(
            lambda checked=False: self._on_connect_clicked()
        )
        self._menu.addAction(self._connect_action)

        self._menu.addSeparator()

        # Settings action
        settings_action = QAction("Settings", self._menu)
        settings_action.triggered.connect(self.signals.settings_requested.emit)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self.signals.quit_requested.emit)
        self._menu.addAction(quit_action)

    def _add_menu_item(self, menu: QMenu, item: TrayMenuItem) -> None:
        """Add a menu item to the menu recursively."""
        if item.children:
            # Create submenu
            submenu = menu.addMenu(item.label)
            for child in item.children:
                self._add_menu_item(submenu, child)
        else:
            # Create action
            action = QAction(item.label, menu)
            if item.callback:
                action.triggered.connect(item.callback)
            else:
                action.setEnabled(False)
            menu.addAction(action)

        if item.separator_after:
            menu.addSeparator()

    def set_plugin_items(self, items: list[TrayMenuItem]) -> None:
        """Set plugin menu items and rebuild the menu."""
        self._plugin_items = items
        self._build_menu()

    def rebuild_menu(self) -> None:
        """Rebuild the menu (e.g., after plugin changes)."""
        self._build_menu()

    def show(self) -> None:
        """Show the tray icon."""
        self._tray_icon.show()
        logger.info("Tray icon shown")

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray_icon.hide()
        logger.info("Tray icon hidden")

    def set_tooltip(self, tooltip: str) -> None:
        """Set the tray icon tooltip."""
        self._tray_icon.setToolTip(tooltip)

    def _get_connect_button_text(self) -> str:
        """Get button text based on connection status."""
        if self._connection_status == ConnectionStatus.CONNECTING:
            return "Connecting..."
        elif self._connection_status == ConnectionStatus.CONNECTED:
            return "Disconnect"
        else:  # DISCONNECTED or ERROR
            return "Connect"

    def _on_connect_clicked(self) -> None:
        """Handle connect/disconnect button click."""
        if self._event_bus:
            from core.event_bus import Topics
            if self._connection_status == ConnectionStatus.CONNECTED:
                self._event_bus.publish(Topics.UI_DISCONNECT_REQUESTED, None)
            else:
                self._event_bus.publish(Topics.UI_CONNECT_REQUESTED, None)

    def set_connection_status(self, status: ConnectionStatus) -> None:
        """Update tray icon, tooltip, and menu based on connection status.

        Args:
            status: Connection status to set
        """
        self._connection_status = status

        # Update icon
        icon_map = {
            ConnectionStatus.CONNECTING: "icon-connecting.png",
            ConnectionStatus.CONNECTED: "icon-connected.png",
            ConnectionStatus.DISCONNECTED: "icon-disconnected.png",
            ConnectionStatus.ERROR: "icon-error.png",
        }
        icon_path = self.assets_dir / icon_map[status]
        if icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(icon_path)))

        # Update tooltip
        tooltip_map = {
            ConnectionStatus.CONNECTING: "System Agent - Connecting...",
            ConnectionStatus.CONNECTED: "System Agent - Connected",
            ConnectionStatus.DISCONNECTED: "System Agent - Disconnected",
            ConnectionStatus.ERROR: "System Agent - Error",
        }
        self._tray_icon.setToolTip(tooltip_map[status])

        # Update connect button
        if self._connect_action:
            self._connect_action.setText(self._get_connect_button_text())
            self._connect_action.setEnabled(status != ConnectionStatus.CONNECTING)

        logger.info(f"Connection status changed to: {status.value}")

    def show_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration: int = DEFAULT_NOTIFICATION_DURATION_MS,
        notification_type: NotificationType = NotificationType.SYSTEM
    ) -> bool | None:
        """
        Show a notification message (cross-platform).

        Args:
            title: Notification title
            message: Notification message
            icon: Icon type for the notification
            duration: Duration in ms (for system notifications)
            notification_type: SYSTEM (non-blocking) or MODAL (blocking dialog)

        Returns:
            For MODAL: True if OK clicked, False if cancelled, None otherwise
            For SYSTEM: None
        """
        if notification_type == NotificationType.MODAL:
            return self._show_modal_dialog(title, message, icon)

        # System notification (non-blocking)
        system = platform.system()

        if system == PLATFORM_MACOS:
            self._show_macos_notification(title, message)
        elif system == PLATFORM_LINUX:
            self._show_linux_notification(title, message)
        elif system == PLATFORM_WINDOWS:
            self._show_windows_notification(title, message, icon, duration)
        else:
            # Fallback to Qt
            self._tray_icon.showMessage(title, message, icon, duration)

        return None

    def _show_modal_dialog(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information
    ) -> bool:
        """Show a modal dialog that requires user action."""
        # Map tray icon type to QMessageBox icon
        icon_map = {
            QSystemTrayIcon.MessageIcon.NoIcon: QMessageBox.Icon.NoIcon,
            QSystemTrayIcon.MessageIcon.Information: QMessageBox.Icon.Information,
            QSystemTrayIcon.MessageIcon.Warning: QMessageBox.Icon.Warning,
            QSystemTrayIcon.MessageIcon.Critical: QMessageBox.Icon.Critical,
        }
        msg_icon = icon_map.get(icon, QMessageBox.Icon.Information)

        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(msg_icon)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        # Make window stay on top
        msg_box.setWindowFlags(
            msg_box.windowFlags() |
            msg_box.windowFlags().WindowStaysOnTopHint
        )

        result = msg_box.exec()
        logger.info(f"Modal dialog closed: {title}")

        return result == QMessageBox.StandardButton.Ok

    def _show_macos_notification(self, title: str, message: str) -> None:
        """Show a native macOS notification."""
        macos_cmds = MacOSCommands()

        # Try terminal-notifier first (most reliable)
        try:
            result = subprocess.run(
                [macos_cmds.TERMINAL_NOTIFIER, "-title", title, "-message", message, "-sound", "default"],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT
            )
            if result.returncode == 0:
                logger.info(f"Notification shown via {macos_cmds.TERMINAL_NOTIFIER}")
                return
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            logger.warning(f"{macos_cmds.TERMINAL_NOTIFIER} timed out")

        # Fallback to osascript
        title_escaped = title.replace('"', '\\"').replace("'", "\\'")
        message_escaped = message.replace('"', '\\"').replace("'", "\\'")
        script = f'display notification "{message_escaped}" with title "{title_escaped}"'
        try:
            subprocess.run(
                [macos_cmds.OSASCRIPT, "-e", script],
                check=True,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT
            )
            logger.info(f"Notification shown via {macos_cmds.OSASCRIPT}")
        except subprocess.TimeoutExpired:
            logger.warning(f"{macos_cmds.OSASCRIPT} timed out, falling back to Qt")
            self._tray_icon.showMessage(title, message)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Failed to show macOS notification: {e}")
            # Last resort: Qt
            self._tray_icon.showMessage(title, message)

    def _show_linux_notification(self, title: str, message: str) -> None:
        """Show a native Linux notification using notify-send."""
        try:
            subprocess.run(
                ["notify-send", title, message, "-a", "System Agent"],
                check=True,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT
            )
            logger.info(f"Notification shown via notify-send")
        except subprocess.TimeoutExpired:
            logger.warning(f"notify-send timed out, falling back to Qt")
            self._tray_icon.showMessage(title, message)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"notify-send failed: {e}, falling back to Qt")
            self._tray_icon.showMessage(title, message)

    def _show_windows_notification(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon,
        duration: int
    ) -> None:
        """Show a Windows notification."""
        # On Windows, QSystemTrayIcon.showMessage() usually works well
        # when the tray icon is visible
        if self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, icon, duration)
            logger.info(f"Notification shown via Qt tray")
        else:
            # Fallback: PowerShell toast (Windows 10+)
            try:
                ps_script = f'''
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
                $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
                $xml.GetElementsByTagName("text")[0].AppendChild($xml.CreateTextNode("{title}")) | Out-Null
                $xml.GetElementsByTagName("text")[1].AppendChild($xml.CreateTextNode("{message}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("System Agent").Show($toast)
                '''
                subprocess.run(
                    ["powershell", "-Command", ps_script],
                    check=True,
                    capture_output=True
                )
                logger.info(f"Notification shown via PowerShell toast")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                logger.error(f"Failed to show Windows notification: {e}")

    @property
    def tray_icon(self) -> QSystemTrayIcon:
        """Get the underlying QSystemTrayIcon."""
        return self._tray_icon

    def _setup_event_bus_integration(self) -> None:
        """Set up EventBus integration for Qt signals.

        Publishes UI events to EventBus when signals are emitted.
        """
        from core.event_bus import Topics

        # Publish to EventBus when signals are emitted
        self.signals.settings_requested.connect(
            lambda: self._event_bus.publish(Topics.UI_SETTINGS_REQUESTED, None)
        )
        self.signals.quit_requested.connect(
            lambda: self._event_bus.publish(Topics.UI_QUIT_REQUESTED, None)
        )

    def on_settings_requested(self, callback: Callable[[], None]) -> None:
        """Register a callback for settings request.

        Note: Only needed when EventBus is not used (backward compatibility).
        """
        self.signals.settings_requested.connect(callback)

    def on_quit_requested(self, callback: Callable[[], None]) -> None:
        """Register a callback for quit request.

        Note: Only needed when EventBus is not used (backward compatibility).
        """
        self.signals.quit_requested.connect(callback)
