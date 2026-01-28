"""Tests for ui.tray module."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from ui.tray import TrayManager, ConnectionStatus, NotificationType


@pytest.fixture
def mock_qt_app():
    """Mock Qt application."""
    app = MagicMock()
    app.style().standardIcon.return_value = MagicMock()
    return app


@pytest.fixture
def mock_event_bus():
    """Mock EventBus."""
    return MagicMock()


@pytest.fixture
def tmp_assets_dir(tmp_path):
    """Create temporary assets directory with icons."""
    assets = tmp_path / "assets"
    assets.mkdir()
    # Create mock icon files
    (assets / "icon.png").write_bytes(b"fake png")
    (assets / "icon-connecting.png").write_bytes(b"fake png")
    (assets / "icon-connected.png").write_bytes(b"fake png")
    (assets / "icon-disconnected.png").write_bytes(b"fake png")
    (assets / "icon-error.png").write_bytes(b"fake png")
    return assets


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_connection_status_values(self):
        """Test ConnectionStatus enum values."""
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.ERROR.value == "error"


class TestTrayManagerConnectionStatus:
    """Tests for TrayManager connection status functionality."""

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_initial_connection_status(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test initial connection status is DISCONNECTED."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)
        assert tray._connection_status == ConnectionStatus.DISCONNECTED

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_connected(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status for CONNECTED."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        tray.set_connection_status(ConnectionStatus.CONNECTED)

        assert tray._connection_status == ConnectionStatus.CONNECTED
        # Check tooltip was set
        tray._tray_icon.setToolTip.assert_called_with("Agimate Desktop - Connected")

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_disconnected(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status for DISCONNECTED."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        tray.set_connection_status(ConnectionStatus.DISCONNECTED)

        assert tray._connection_status == ConnectionStatus.DISCONNECTED
        tray._tray_icon.setToolTip.assert_called_with("Agimate Desktop - Disconnected")

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_connecting(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status for CONNECTING."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        tray.set_connection_status(ConnectionStatus.CONNECTING)

        assert tray._connection_status == ConnectionStatus.CONNECTING
        tray._tray_icon.setToolTip.assert_called_with("Agimate Desktop - Connecting...")

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_error(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status for ERROR."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        tray.set_connection_status(ConnectionStatus.ERROR)

        assert tray._connection_status == ConnectionStatus.ERROR
        tray._tray_icon.setToolTip.assert_called_with("Agimate Desktop - Error")

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_updates_icon(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status updates icon."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        tray.set_connection_status(ConnectionStatus.CONNECTED)

        # Icon should have been set
        tray._tray_icon.setIcon.assert_called()

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_set_connection_status_updates_connect_button(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test set_connection_status updates connect button text."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        # Set up mock connect action
        mock_connect_action = MagicMock()
        tray._connect_action = mock_connect_action

        tray.set_connection_status(ConnectionStatus.CONNECTED)

        mock_connect_action.setText.assert_called_with("Disconnect")
        mock_connect_action.setEnabled.assert_called_with(True)

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_connect_button_disabled_when_connecting(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test connect button is disabled when CONNECTING."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)

        mock_connect_action = MagicMock()
        tray._connect_action = mock_connect_action

        tray.set_connection_status(ConnectionStatus.CONNECTING)

        mock_connect_action.setText.assert_called_with("Connecting...")
        mock_connect_action.setEnabled.assert_called_with(False)


class TestTrayManagerConnectButton:
    """Tests for Connect/Disconnect button functionality."""

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_get_connect_button_text_connecting(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test button text when connecting."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)
        tray._connection_status = ConnectionStatus.CONNECTING
        assert tray._get_connect_button_text() == "Connecting..."

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_get_connect_button_text_connected(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test button text when connected."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)
        tray._connection_status = ConnectionStatus.CONNECTED
        assert tray._get_connect_button_text() == "Disconnect"

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_get_connect_button_text_disconnected(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test button text when disconnected."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)
        tray._connection_status = ConnectionStatus.DISCONNECTED
        assert tray._get_connect_button_text() == "Connect"

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_get_connect_button_text_error(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test button text when error."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir)
        tray._connection_status = ConnectionStatus.ERROR
        assert tray._get_connect_button_text() == "Connect"

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_on_connect_clicked_publishes_connect_event(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir, mock_event_bus):
        """Test clicking Connect publishes UI_CONNECT_REQUESTED."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir, event_bus=mock_event_bus)
        tray._connection_status = ConnectionStatus.DISCONNECTED

        tray._on_connect_clicked()

        from core.event_bus import Topics
        mock_event_bus.publish.assert_called_with(Topics.UI_CONNECT_REQUESTED, None)

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_on_connect_clicked_publishes_disconnect_event(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir, mock_event_bus):
        """Test clicking Disconnect publishes UI_DISCONNECT_REQUESTED."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir, event_bus=mock_event_bus)
        tray._connection_status = ConnectionStatus.CONNECTED

        tray._on_connect_clicked()

        from core.event_bus import Topics
        mock_event_bus.publish.assert_called_with(Topics.UI_DISCONNECT_REQUESTED, None)

    @patch("ui.tray.QAction")
    @patch("ui.tray.QSystemTrayIcon")
    @patch("ui.tray.QMenu")
    def test_on_connect_clicked_no_event_bus(self, mock_menu, mock_tray_icon, mock_action, mock_qt_app, tmp_assets_dir):
        """Test clicking Connect without event bus does nothing."""
        tray = TrayManager(mock_qt_app, tmp_assets_dir, event_bus=None)
        tray._connection_status = ConnectionStatus.DISCONNECTED

        # Should not raise
        tray._on_connect_clicked()


class TestTrayManagerNotificationType:
    """Tests for NotificationType enum."""

    def test_notification_type_values(self):
        """Test NotificationType enum values."""
        assert NotificationType.SYSTEM.value == "system"
        assert NotificationType.MODAL.value == "modal"
