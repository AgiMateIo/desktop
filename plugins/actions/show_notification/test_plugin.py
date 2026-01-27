"""Tests for show_notification action plugin."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from .plugin import ShowNotificationAction


class TestShowNotificationInit:
    """Test cases for ShowNotificationAction initialization."""

    def test_init(self, tmp_path):
        """Test ShowNotificationAction initialization."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)

        assert plugin.plugin_dir == plugin_dir
        assert plugin.plugin_id == "show_notification"
        assert plugin.name == "Show Notification"
        assert plugin._tray_manager is None

    def test_get_supported_actions(self, tmp_path):
        """Test get_supported_actions() returns correct actions."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)

        actions = plugin.get_supported_actions()

        assert "NOTIFICATION" in actions
        assert "NOTIFICATION_MODAL" in actions
        assert len(actions) == 2

    def test_set_tray_manager(self, tmp_path):
        """Test set_tray_manager() sets the tray manager."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        mock_tray_manager = Mock()

        plugin.set_tray_manager(mock_tray_manager)

        assert plugin._tray_manager == mock_tray_manager


class TestShowNotificationLifecycle:
    """Test cases for plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize(self, tmp_path):
        """Test initialize() method."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)

        await plugin.initialize()

        # Should not crash

    @pytest.mark.asyncio
    async def test_shutdown(self, tmp_path):
        """Test shutdown() method."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)

        await plugin.initialize()
        await plugin.shutdown()

        # Should not crash


class TestNotificationExecution:
    """Test cases for notification execution."""

    @pytest.mark.asyncio
    async def test_execute_system_notification_success(self, tmp_path):
        """Test execute() with system notification."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        # Mock tray manager
        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test Title",
            "message": "Test Message",
            "duration": 3000
        })

        assert result is True
        mock_tray.show_message.assert_called_once()

        # Verify call arguments
        call_args = mock_tray.show_message.call_args
        assert call_args.kwargs["title"] == "Test Title"
        assert call_args.kwargs["message"] == "Test Message"
        assert call_args.kwargs["duration"] == 3000

    @pytest.mark.asyncio
    async def test_execute_modal_notification(self, tmp_path):
        """Test execute() with modal notification."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION_MODAL", {
            "title": "Modal Test",
            "message": "Modal Message"
        })

        assert result is True
        mock_tray.show_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_without_tray_manager(self, tmp_path):
        """Test execute() without tray manager set."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        # No tray manager set
        result = await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": "Test"
        })

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_without_message(self, tmp_path):
        """Test execute() without message parameter."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test"
            # No message
        })

        assert result is False
        mock_tray.show_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_empty_message(self, tmp_path):
        """Test execute() with empty message."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": ""
        })

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_unsupported_action_type(self, tmp_path):
        """Test execute() with unsupported action type."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("UNKNOWN_ACTION", {
            "title": "Test",
            "message": "Test"
        })

        assert result is False
        mock_tray.show_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_modal_via_parameter(self, tmp_path):
        """Test execute() with modal parameter instead of MODAL action type."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": "Test Message",
            "modal": True
        })

        assert result is True
        mock_tray.show_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_default_title(self, tmp_path):
        """Test execute() uses default title when not provided."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "message": "Test Message"
            # No title
        })

        assert result is True
        call_args = mock_tray.show_message.call_args
        assert call_args.kwargs["title"] == "Agimate"  # Default title

    @pytest.mark.asyncio
    async def test_execute_with_default_duration(self, tmp_path):
        """Test execute() uses default duration when not provided."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": "Test Message"
            # No duration
        })

        assert result is True
        call_args = mock_tray.show_message.call_args
        assert call_args.kwargs["duration"] == 5000  # Default duration

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self, tmp_path):
        """Test execute() handles exceptions gracefully."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)
        await plugin.initialize()

        # Mock tray that raises exception
        mock_tray = Mock()
        mock_tray.show_message = Mock(side_effect=Exception("Test error"))
        plugin.set_tray_manager(mock_tray)

        result = await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": "Test Message"
        })

        assert result is False


class TestConfiguration:
    """Test cases for plugin configuration."""

    @pytest.mark.asyncio
    async def test_custom_default_title_from_config(self, tmp_path):
        """Test using custom default title from config."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        import json
        config = {
            "enabled": True,
            "default_title": "Custom App Name"
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = ShowNotificationAction(plugin_dir)
        plugin.load_config()
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        await plugin.execute("NOTIFICATION", {
            "message": "Test"
        })

        call_args = mock_tray.show_message.call_args
        assert call_args.kwargs["title"] == "Custom App Name"

    @pytest.mark.asyncio
    async def test_custom_default_duration_from_config(self, tmp_path):
        """Test using custom default duration from config."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        import json
        config = {
            "enabled": True,
            "default_duration": 10000
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = ShowNotificationAction(plugin_dir)
        plugin.load_config()
        await plugin.initialize()

        mock_tray = Mock()
        mock_tray.show_message = Mock(return_value=True)
        plugin.set_tray_manager(mock_tray)

        await plugin.execute("NOTIFICATION", {
            "title": "Test",
            "message": "Test"
        })

        call_args = mock_tray.show_message.call_args
        assert call_args.kwargs["duration"] == 10000


class TestBackwardCompatibility:
    """Test cases for backward compatibility."""

    def test_set_tray_icon_deprecated(self, tmp_path):
        """Test deprecated set_tray_icon() doesn't crash."""
        plugin_dir = tmp_path / "show_notification"
        plugin_dir.mkdir()

        plugin = ShowNotificationAction(plugin_dir)

        # Should not crash
        mock_tray_icon = Mock()
        plugin.set_tray_icon(mock_tray_icon)
