"""Tests for screenshot tool plugin."""

import json
import base64
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from .plugin import ScreenshotTool


def _make_plugin(tmp_path, config=None):
    plugin_dir = tmp_path / "screenshot"
    plugin_dir.mkdir(exist_ok=True)
    if config is not None:
        (plugin_dir / "config.json").write_text(json.dumps(config))
    plugin = ScreenshotTool(plugin_dir)
    plugin.load_config()
    return plugin


def _mock_pixmap(width=1920, height=1080, is_null=False):
    px = Mock()
    px.isNull.return_value = is_null
    px.width.return_value = width
    px.height.return_value = height
    px.save.return_value = True
    px.copy.return_value = px
    return px


def _mock_screen(pixmap=None):
    screen = Mock()
    screen.grabWindow.return_value = pixmap or _mock_pixmap()
    return screen


class TestScreenshotInit:

    def test_init(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin.name == "Screenshot"
        assert plugin.plugin_id == "screenshot"
        assert plugin._qt_available is False

    def test_get_supported_tools(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        tools = plugin.get_supported_tools()
        assert "desktop.tool.screenshot.fullscreen" in tools
        assert "desktop.tool.screenshot.window" in tools
        assert "desktop.tool.screenshot.region" in tools
        assert len(tools) == 3

    def test_status_disabled(self, tmp_path):
        plugin = _make_plugin(tmp_path, {"enabled": False, "default_format": "png", "default_quality": 85})
        assert plugin.status == "Disabled"

    def test_status_qt_unavailable(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin.status == "Qt not available"

    def test_status_running(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True
        assert plugin.status == "Running"

    def test_capabilities(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        caps = plugin.get_capabilities()
        assert "desktop.tool.screenshot.fullscreen" in caps
        assert "desktop.tool.screenshot.window" in caps
        assert "desktop.tool.screenshot.region" in caps
        assert "params" in caps["desktop.tool.screenshot.fullscreen"]


class TestConfigValidation:

    def test_valid_png(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "png", "default_quality": 85}
        valid, _ = plugin.validate_config()
        assert valid is True

    def test_valid_jpeg(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "jpeg", "default_quality": 60}
        valid, _ = plugin.validate_config()
        assert valid is True

    def test_invalid_format(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "gif", "default_quality": 85}
        valid, err = plugin.validate_config()
        assert valid is False
        assert "default_format" in err

    def test_invalid_quality_zero(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "png", "default_quality": 0}
        valid, _ = plugin.validate_config()
        assert valid is False

    def test_invalid_quality_over_100(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "png", "default_quality": 101}
        valid, _ = plugin.validate_config()
        assert valid is False

    def test_invalid_quality_string(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._config = {"enabled": True, "default_format": "png", "default_quality": "high"}
        valid, _ = plugin.validate_config()
        assert valid is False


class TestDetection:

    @pytest.mark.asyncio
    async def test_initialize_with_qt(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        mock_app = Mock()
        mock_app.screens.return_value = [Mock()]

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.instance.return_value = mock_app
            await plugin.initialize()

        assert plugin._qt_available is True

    @pytest.mark.asyncio
    async def test_initialize_without_qt(self, tmp_path):
        plugin = _make_plugin(tmp_path)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.instance.return_value = None
            await plugin.initialize()

        assert plugin._qt_available is False

    @pytest.mark.asyncio
    async def test_initialize_no_screens(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        mock_app = Mock()
        mock_app.screens.return_value = []

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.instance.return_value = mock_app
            await plugin.initialize()

        assert plugin._qt_available is False


class TestNotAvailable:

    @pytest.mark.asyncio
    async def test_execute_when_qt_unavailable(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = False

        result = await plugin.execute("desktop.tool.screenshot.fullscreen", {})
        assert result.success is False
        assert "not available" in result.error


class TestFullscreenCapture:

    @pytest.mark.asyncio
    async def test_success(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen()

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"fakepng"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute("desktop.tool.screenshot.fullscreen", {})

        assert result.success is True
        assert "image" in result.data
        assert result.data["format"] == "png"
        assert result.data["width"] == 1920
        assert result.data["height"] == 1080
        assert result.data["screen_index"] == 0

    @pytest.mark.asyncio
    async def test_screen_index_out_of_range(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.screens.return_value = [Mock()]
            result = await plugin.execute("desktop.tool.screenshot.fullscreen", {"screen_index": 5})

        assert result.success is False
        assert "out of range" in result.error

    @pytest.mark.asyncio
    async def test_negative_screen_index(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.screens.return_value = [Mock()]
            result = await plugin.execute("desktop.tool.screenshot.fullscreen", {"screen_index": -1})

        assert result.success is False
        assert "out of range" in result.error

    @pytest.mark.asyncio
    async def test_null_pixmap(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen(_mock_pixmap(is_null=True))

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute("desktop.tool.screenshot.fullscreen", {})

        assert result.success is False
        assert "null" in result.error.lower()

    @pytest.mark.asyncio
    async def test_jpeg_format(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen()

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"fakejpeg") as mock_enc:
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"format": "jpeg", "quality": 70},
            )

        assert result.success is True
        assert result.data["format"] == "jpeg"
        _, called_fmt, called_q = mock_enc.call_args[0]
        assert called_fmt == "jpeg"
        assert called_q == 70

    @pytest.mark.asyncio
    async def test_second_screen(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen0 = _mock_screen()
        screen1 = _mock_screen(_mock_pixmap(2560, 1440))

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen0, screen1]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen", {"screen_index": 1}
            )

        assert result.success is True
        assert result.data["screen_index"] == 1
        assert result.data["width"] == 2560


class TestWindowCapture:

    @pytest.mark.asyncio
    async def test_with_explicit_window_id(self, tmp_path):
        plugin = _make_plugin(tmp_path, {"enabled": True, "allow_arbitrary_window_id": True})
        plugin._qt_available = True

        screen = _mock_screen(_mock_pixmap(800, 600))

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.primaryScreen.return_value = screen
            result = await plugin.execute(
                "desktop.tool.screenshot.window", {"window_id": 12345}
            )

        assert result.success is True
        screen.grabWindow.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_window_id_rejected_by_default(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute(
            "desktop.tool.screenshot.window", {"window_id": 12345}
        )

        assert result.success is False
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fallback_to_active_window(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen()
        mock_active = Mock()
        mock_active.winId.return_value = 99999

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.primaryScreen.return_value = screen
            MockQApp.activeWindow.return_value = mock_active
            result = await plugin.execute("desktop.tool.screenshot.window", {})

        assert result.success is True
        screen.grabWindow.assert_called_once_with(99999)

    @pytest.mark.asyncio
    async def test_fallback_to_fullscreen(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen()

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.primaryScreen.return_value = screen
            MockQApp.activeWindow.return_value = None
            result = await plugin.execute("desktop.tool.screenshot.window", {})

        assert result.success is True
        screen.grabWindow.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_null_pixmap(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        screen = _mock_screen(_mock_pixmap(is_null=True))

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp:
            MockQApp.primaryScreen.return_value = screen
            MockQApp.activeWindow.return_value = None
            result = await plugin.execute("desktop.tool.screenshot.window", {})

        assert result.success is False


class TestRegionCapture:

    @pytest.mark.asyncio
    async def test_success(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        full_px = _mock_pixmap(1920, 1080)
        region_px = _mock_pixmap(400, 300)
        full_px.copy.return_value = region_px
        screen = _mock_screen(full_px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.region",
                {"x": 100, "y": 200, "width": 400, "height": 300},
            )

        assert result.success is True
        assert result.data["width"] == 400
        assert result.data["height"] == 300
        assert result.data["region"] == {"x": 100, "y": 200, "width": 400, "height": 300}

    @pytest.mark.asyncio
    async def test_missing_x(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute(
            "desktop.tool.screenshot.region",
            {"y": 0, "width": 100, "height": 100},
        )
        assert result.success is False
        assert "'x'" in result.error

    @pytest.mark.asyncio
    async def test_missing_height(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute(
            "desktop.tool.screenshot.region",
            {"x": 0, "y": 0, "width": 100},
        )
        assert result.success is False
        assert "'height'" in result.error

    @pytest.mark.asyncio
    async def test_zero_width(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute(
            "desktop.tool.screenshot.region",
            {"x": 0, "y": 0, "width": 0, "height": 100},
        )
        assert result.success is False
        assert "positive" in result.error

    @pytest.mark.asyncio
    async def test_negative_height(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute(
            "desktop.tool.screenshot.region",
            {"x": 0, "y": 0, "width": 100, "height": -50},
        )
        assert result.success is False
        assert "positive" in result.error


class TestSaveToDisk:

    @pytest.mark.asyncio
    async def test_save_path_success(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        save_target = tmp_path / "out" / "shot.png"
        px = _mock_pixmap()
        screen = _mock_screen(px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"save_path": str(save_target)},
            )

        assert result.success is True
        assert result.data.get("saved_path") == str(save_target)

    @pytest.mark.asyncio
    async def test_save_path_returns_resolved(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        save_target = tmp_path / "out" / "shot.png"
        px = _mock_pixmap()
        screen = _mock_screen(px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"save_path": str(save_target)},
            )

        assert result.success is True
        assert result.data["saved_path"] == str(save_target.resolve())

    @pytest.mark.asyncio
    async def test_save_path_outside_save_directory(self, tmp_path):
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        plugin = _make_plugin(tmp_path, {"enabled": True, "save_directory": str(allowed_dir)})
        plugin._qt_available = True

        px = _mock_pixmap()
        screen = _mock_screen(px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"save_path": "/etc/evil.png"},
            )

        assert result.success is True
        assert result.data.get("saved_path") is None
        assert "Access denied" in result.data.get("save_error", "")

    @pytest.mark.asyncio
    async def test_save_path_within_save_directory(self, tmp_path):
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        plugin = _make_plugin(tmp_path, {"enabled": True, "save_directory": str(allowed_dir)})
        plugin._qt_available = True

        save_target = allowed_dir / "shot.png"
        px = _mock_pixmap()
        screen = _mock_screen(px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"save_path": str(save_target)},
            )

        assert result.success is True
        assert result.data.get("saved_path") is not None

    @pytest.mark.asyncio
    async def test_save_failure_non_fatal(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        px = _mock_pixmap()
        px.save.return_value = False
        screen = _mock_screen(px)

        with patch("plugins.tools.screenshot.plugin.QApplication") as MockQApp, \
             patch.object(plugin, "_pixmap_to_bytes", return_value=b"data"):
            MockQApp.screens.return_value = [screen]
            result = await plugin.execute(
                "desktop.tool.screenshot.fullscreen",
                {"save_path": "/some/path/shot.png"},
            )

        assert result.success is True
        assert result.data.get("saved_path") is None
        assert "save_error" in result.data


class TestFormatAndQuality:

    def test_resolve_format_default(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_format({}) == "png"

    def test_resolve_format_jpeg(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_format({"format": "jpeg"}) == "jpeg"

    def test_resolve_format_invalid_falls_back(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_format({"format": "bmp"}) == "png"

    def test_resolve_quality_default(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_quality({}) == 85

    def test_resolve_quality_custom(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_quality({"quality": 50}) == 50

    def test_resolve_quality_clamped_low(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_quality({"quality": -10}) == 1

    def test_resolve_quality_clamped_high(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_quality({"quality": 200}) == 100

    def test_resolve_quality_invalid_type(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        assert plugin._resolve_quality({"quality": "max"}) == 85


class TestUnknownTool:

    @pytest.mark.asyncio
    async def test_unknown_tool_type(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        plugin._qt_available = True

        result = await plugin.execute("desktop.tool.screenshot.unknown", {})
        assert result.success is False
        assert "Unknown tool" in result.error


class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown(self, tmp_path):
        plugin = _make_plugin(tmp_path)
        await plugin.shutdown()
