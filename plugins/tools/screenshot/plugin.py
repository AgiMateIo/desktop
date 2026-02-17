"""Screenshot tool plugin using PySide6 QScreen."""

import base64
import logging
import platform
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from core.plugin_base import ToolPlugin
from core.tool_types import (
    TOOL_SCREENSHOT_FULLSCREEN,
    TOOL_SCREENSHOT_WINDOW,
    TOOL_SCREENSHOT_REGION,
)
from core.models import ToolResult

logger = logging.getLogger(__name__)

DEFAULT_JPEG_QUALITY = 85
SUPPORTED_FORMATS = {"png", "jpeg"}


class ScreenshotTool(ToolPlugin):
    """Tool plugin for taking screenshots using PySide6 QScreen."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._system = platform.system()
        self._qt_available = False

    @property
    def name(self) -> str:
        return "Screenshot"

    @property
    def description(self) -> str:
        return "Captures screenshots: full screen, specific window, or screen region"

    @property
    def status(self) -> str:
        if not self.enabled:
            return "Disabled"
        if not self._qt_available:
            return "Qt not available"
        return "Running"

    def get_supported_tools(self) -> list[str]:
        return [
            TOOL_SCREENSHOT_FULLSCREEN,
            TOOL_SCREENSHOT_WINDOW,
            TOOL_SCREENSHOT_REGION,
        ]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            TOOL_SCREENSHOT_FULLSCREEN: {
                "params": ["screen_index", "format", "quality", "save_path"],
                "description": (
                    "Capture the full screen. "
                    "screen_index (int, default 0) selects the monitor. "
                    "format: 'png' (default) or 'jpeg'. "
                    "quality: JPEG quality 1-100 (default 85). "
                    "save_path: optional absolute path to save the file."
                ),
            },
            TOOL_SCREENSHOT_WINDOW: {
                "params": ["window_id", "format", "quality", "save_path"],
                "description": (
                    "Capture a specific window by its native window ID (int). "
                    "Omit window_id to capture the currently active Qt window. "
                    "format: 'png' (default) or 'jpeg'. "
                    "quality: JPEG quality 1-100 (default 85). "
                    "save_path: optional absolute path to save the file."
                ),
            },
            TOOL_SCREENSHOT_REGION: {
                "params": ["x", "y", "width", "height", "screen_index", "format", "quality", "save_path"],
                "description": (
                    "Capture a rectangular region of the screen. "
                    "x, y: top-left corner in screen coordinates (required). "
                    "width, height: region size in pixels (required). "
                    "screen_index (int, default 0) selects the monitor. "
                    "format: 'png' (default) or 'jpeg'. "
                    "quality: JPEG quality 1-100 (default 85). "
                    "save_path: optional absolute path to save the file."
                ),
            },
        }

    def validate_config(self) -> tuple[bool, str]:
        fmt = self._config.get("default_format", "png")
        if fmt not in SUPPORTED_FORMATS:
            return False, f"default_format must be one of {sorted(SUPPORTED_FORMATS)}"
        quality = self._config.get("default_quality", DEFAULT_JPEG_QUALITY)
        if not isinstance(quality, int) or not (1 <= quality <= 100):
            return False, "default_quality must be an integer between 1 and 100"
        return True, ""

    async def initialize(self) -> None:
        self._detect_qt()
        if self._qt_available:
            logger.info("ScreenshotTool initialized with QScreen")
        else:
            logger.warning("ScreenshotTool: QApplication not available")

    def _detect_qt(self) -> None:
        try:
            app = QApplication.instance()
            if app is not None and len(app.screens()) > 0:
                self._qt_available = True
        except Exception as e:
            logger.error(f"ScreenshotTool Qt check failed: {e}")
            self._qt_available = False

    async def shutdown(self) -> None:
        logger.info("ScreenshotTool shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        if not self._qt_available:
            return ToolResult(success=False, error="Screenshot not available: QApplication not running")

        if tool_type == TOOL_SCREENSHOT_FULLSCREEN:
            return self._capture_fullscreen(parameters)
        elif tool_type == TOOL_SCREENSHOT_WINDOW:
            return self._capture_window(parameters)
        elif tool_type == TOOL_SCREENSHOT_REGION:
            return self._capture_region(parameters)

        return ToolResult(success=False, error=f"Unknown tool: {tool_type}")

    def _capture_fullscreen(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            screen_index = parameters.get("screen_index", 0)
            screens = QApplication.screens()

            if screen_index < 0 or screen_index >= len(screens):
                return ToolResult(
                    success=False,
                    error=f"screen_index {screen_index} out of range (found {len(screens)} screens)",
                )

            screen = screens[screen_index]
            pixmap = screen.grabWindow(0)

            if pixmap.isNull():
                return ToolResult(success=False, error="Screen grab returned null pixmap")

            return self._build_result(pixmap, parameters, screen_index=screen_index)

        except Exception as e:
            logger.error(f"Fullscreen capture error: {e}")
            return ToolResult(success=False, error=str(e))

    def _capture_window(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            win_id = parameters.get("window_id")
            screen = QApplication.primaryScreen()

            if win_id is not None:
                win_id = int(win_id)

                # On macOS, use native Quartz API for capturing other app windows
                # QScreen.grabWindow() crashes (SIGSEGV) with foreign window IDs
                if self._system == "Darwin":
                    return self._capture_window_macos(win_id, parameters)

                pixmap = screen.grabWindow(win_id)
            else:
                active = QApplication.activeWindow()
                if active is not None:
                    pixmap = screen.grabWindow(int(active.winId()))
                else:
                    logger.warning("No active window found; falling back to full screen capture")
                    pixmap = screen.grabWindow(0)

            if pixmap.isNull():
                return ToolResult(success=False, error="Window grab returned null pixmap")

            return self._build_result(pixmap, parameters)

        except Exception as e:
            logger.error(f"Window capture error: {e}")
            return ToolResult(success=False, error=str(e))

    def _capture_window_macos(self, win_id: int, parameters: dict[str, Any]) -> ToolResult:
        """Capture a window on macOS using native Quartz API (safe for any app).

        Falls back to cropping a fullscreen grab by window bounds if
        CGWindowListCreateImage fails (e.g. missing Screen Recording permission).
        """
        try:
            import Quartz
            from PySide6.QtGui import QImage, QPixmap

            # Validate the window exists and get its bounds
            info_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionIncludingWindow, win_id
            )
            if not info_list or len(info_list) == 0:
                return ToolResult(
                    success=False,
                    error=f"Window ID {win_id} does not exist or is not accessible",
                )

            # Try native Quartz capture first
            cg_image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                win_id,
                Quartz.kCGWindowImageBoundsIgnoreFraming,
            )

            if cg_image is not None:
                width = Quartz.CGImageGetWidth(cg_image)
                height = Quartz.CGImageGetHeight(cg_image)
                bytes_per_row = Quartz.CGImageGetBytesPerRow(cg_image)

                data_provider = Quartz.CGImageGetDataProvider(cg_image)
                raw_data = Quartz.CGDataProviderCopyData(data_provider)

                q_image = QImage(
                    raw_data, width, height, bytes_per_row,
                    QImage.Format.Format_ARGB32_Premultiplied,
                )
                q_image._raw_data = raw_data

                pixmap = QPixmap.fromImage(q_image)
                if not pixmap.isNull():
                    return self._build_result(pixmap, parameters)

            # Fallback: grab full screen and crop to window bounds
            logger.info(f"Quartz capture failed for window {win_id}, falling back to screen crop")
            bounds_raw = info_list[0].get("kCGWindowBounds", {})
            x = int(bounds_raw.get("X", 0))
            y = int(bounds_raw.get("Y", 0))
            w = int(bounds_raw.get("Width", 0))
            h = int(bounds_raw.get("Height", 0))

            if w <= 0 or h <= 0:
                return ToolResult(success=False, error=f"Window {win_id} has invalid bounds ({w}x{h})")

            # Find which screen contains this window
            from PySide6.QtCore import QRect, QPoint
            screens = QApplication.screens()
            target_screen = None
            for screen in screens:
                geom = screen.geometry()
                if geom.contains(QPoint(x + w // 2, y + h // 2)):
                    target_screen = screen
                    break
            if target_screen is None:
                target_screen = QApplication.primaryScreen()

            full_pixmap = target_screen.grabWindow(0)
            if full_pixmap.isNull():
                return ToolResult(success=False, error="Screen grab returned null pixmap")

            # Convert window coords to screen-local coords
            geom = target_screen.geometry()
            dpr = target_screen.devicePixelRatio()
            local_x = int((x - geom.x()) * dpr)
            local_y = int((y - geom.y()) * dpr)
            local_w = int(w * dpr)
            local_h = int(h * dpr)

            cropped = full_pixmap.copy(QRect(local_x, local_y, local_w, local_h))
            if cropped.isNull():
                return ToolResult(success=False, error=f"Failed to crop window region from screen")

            return self._build_result(cropped, parameters)

        except ImportError:
            return ToolResult(
                success=False,
                error="pyobjc-framework-Quartz is required for window capture on macOS",
            )
        except Exception as e:
            logger.error(f"macOS window capture error: {e}")
            return ToolResult(success=False, error=str(e))

    def _capture_region(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            from PySide6.QtCore import QRect

            for required in ("x", "y", "width", "height"):
                if required not in parameters:
                    return ToolResult(success=False, error=f"Missing required parameter: '{required}'")

            x = int(parameters["x"])
            y = int(parameters["y"])
            width = int(parameters["width"])
            height = int(parameters["height"])

            if width <= 0 or height <= 0:
                return ToolResult(success=False, error="width and height must be positive integers")

            screen_index = parameters.get("screen_index", 0)
            screens = QApplication.screens()

            if screen_index < 0 or screen_index >= len(screens):
                return ToolResult(
                    success=False,
                    error=f"screen_index {screen_index} out of range (found {len(screens)} screens)",
                )

            screen = screens[screen_index]
            full_pixmap = screen.grabWindow(0)

            if full_pixmap.isNull():
                return ToolResult(success=False, error="Screen grab returned null pixmap")

            region_pixmap = full_pixmap.copy(QRect(x, y, width, height))

            if region_pixmap.isNull():
                return ToolResult(
                    success=False,
                    error=f"Region ({x},{y} {width}x{height}) is outside screen bounds",
                )

            return self._build_result(
                region_pixmap, parameters,
                screen_index=screen_index,
                region={"x": x, "y": y, "width": width, "height": height},
            )

        except Exception as e:
            logger.error(f"Region capture error: {e}")
            return ToolResult(success=False, error=str(e))

    @staticmethod
    def _validate_window_id_macos(win_id: int) -> bool:
        """Check that a CGWindowID actually exists before passing it to grabWindow."""
        try:
            import Quartz

            info_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionIncludingWindow, win_id
            )
            return bool(info_list and len(info_list) > 0)
        except Exception:
            return False

    def _build_result(
        self,
        pixmap,
        parameters: dict[str, Any],
        screen_index: int | None = None,
        region: dict[str, int] | None = None,
    ) -> ToolResult:
        fmt = self._resolve_format(parameters)
        quality = self._resolve_quality(parameters)

        image_bytes = self._pixmap_to_bytes(pixmap, fmt, quality)
        if image_bytes is None:
            return ToolResult(success=False, error="Failed to encode image")

        b64_data = base64.b64encode(image_bytes).decode("ascii")

        data: dict[str, Any] = {
            "image": b64_data,
            "format": fmt,
            "width": pixmap.width(),
            "height": pixmap.height(),
            "size_bytes": len(image_bytes),
        }

        if screen_index is not None:
            data["screen_index"] = screen_index

        if region is not None:
            data["region"] = region

        save_path_raw = parameters.get("save_path", self.get_config("default_save_path"))
        if save_path_raw:
            saved, resolved_path, save_error = self._save_to_disk(pixmap, save_path_raw, fmt, quality)
            data["saved_path"] = resolved_path if saved else None
            if not saved:
                data["save_error"] = save_error

        logger.info(
            f"Screenshot captured: {pixmap.width()}x{pixmap.height()} "
            f"format={fmt} size={len(image_bytes)} bytes"
        )
        return ToolResult(success=True, data=data)

    def _pixmap_to_bytes(self, pixmap, fmt: str, quality: int) -> bytes | None:
        try:
            from PySide6.QtCore import QBuffer, QIODeviceBase

            buf = QBuffer()
            buf.open(QIODeviceBase.OpenModeFlag.WriteOnly)

            qt_format = "PNG" if fmt == "png" else "JPEG"
            ok = pixmap.save(buf, qt_format, quality if fmt == "jpeg" else -1)

            buf.close()

            if not ok:
                logger.error(f"pixmap.save() failed for format={qt_format}")
                return None

            return bytes(buf.data())

        except Exception as e:
            logger.error(f"Image encoding error: {e}")
            return None

    def _save_to_disk(
        self, pixmap, path_str: str, fmt: str, quality: int
    ) -> tuple[bool, str | None, str | None]:
        """Save pixmap to disk. Returns (success, resolved_path, error_message)."""
        try:
            save_path = Path(path_str).expanduser().resolve()

            save_directory = self.get_config("save_directory")
            if save_directory:
                allowed_base = Path(save_directory).expanduser().resolve()
                if not str(save_path).startswith(str(allowed_base)):
                    msg = f"Access denied: save_path outside configured save_directory"
                    logger.error(msg)
                    return False, None, msg

            save_path.parent.mkdir(parents=True, exist_ok=True)

            qt_format = "PNG" if fmt == "png" else "JPEG"
            q = quality if fmt == "jpeg" else -1
            ok = pixmap.save(str(save_path), qt_format, q)

            if ok:
                logger.info(f"Screenshot saved to: {save_path}")
                return True, str(save_path), None
            else:
                msg = f"pixmap.save() returned False for path: {save_path}"
                logger.error(msg)
                return False, None, msg

        except Exception as e:
            logger.error(f"Failed to save screenshot to {path_str}: {e}")
            return False, None, str(e)

    def _resolve_format(self, parameters: dict[str, Any]) -> str:
        fmt = parameters.get("format", self.get_config("default_format", "png"))
        fmt = str(fmt).lower()
        return fmt if fmt in SUPPORTED_FORMATS else "png"

    def _resolve_quality(self, parameters: dict[str, Any]) -> int:
        q = parameters.get("quality", self.get_config("default_quality", DEFAULT_JPEG_QUALITY))
        try:
            q = int(q)
            return max(1, min(100, q))
        except (TypeError, ValueError):
            return DEFAULT_JPEG_QUALITY
