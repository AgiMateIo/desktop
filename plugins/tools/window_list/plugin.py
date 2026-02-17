"""Window and application listing tool plugin."""

import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.plugin_base import ToolPlugin
from core.models import ToolResult
from core.tool_types import TOOL_WINDOWS_LIST, TOOL_APPS_LIST
from core.constants import PLATFORM_MACOS, PLATFORM_LINUX, PLATFORM_WINDOWS
from core.platform_commands import LinuxCommands

logger = logging.getLogger(__name__)

ALL_WINDOW_FIELDS = [
    "window_id", "title", "app_name", "pid",
    "bounds", "is_on_screen", "layer",
]

DEFAULT_FIELDS = ["window_id", "title", "app_name", "bounds", "is_on_screen"]


class WindowListTool(ToolPlugin):
    """Tool plugin for listing windows and running applications."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._system = platform.system()
        self._available = False
        self._linux_tool: str | None = None

    @property
    def name(self) -> str:
        return "Window List"

    @property
    def description(self) -> str:
        return "Lists open windows and running applications with bounds, PID, and app name"

    @property
    def status(self) -> str:
        if not self.enabled:
            return "Disabled"
        if not self._available:
            return "No window listing backend available"
        return "Running"

    def get_supported_tools(self) -> list[str]:
        return [TOOL_WINDOWS_LIST, TOOL_APPS_LIST]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            TOOL_WINDOWS_LIST: {
                "params": [
                    "fields", "only_on_screen", "include_minimized",
                    "app_name_filter", "title_filter",
                ],
                "description": (
                    "List open windows with configurable fields. "
                    "fields (list[str]): subset of "
                    f"{ALL_WINDOW_FIELDS}. "
                    "only_on_screen (bool, default true): exclude off-screen windows. "
                    "include_minimized (bool): include minimized windows. "
                    "app_name_filter (str): case-insensitive substring filter on app_name. "
                    "title_filter (str): case-insensitive substring filter on title."
                ),
            },
            TOOL_APPS_LIST: {
                "params": ["include_window_count"],
                "description": (
                    "List running applications with visible windows. "
                    "include_window_count (bool, default true): add window_count per app."
                ),
            },
        }

    def validate_config(self) -> tuple[bool, str]:
        max_w = self._config.get("max_windows", 200)
        if not isinstance(max_w, int) or max_w <= 0:
            return False, "max_windows must be a positive integer"
        df = self._config.get("default_fields", DEFAULT_FIELDS)
        if not isinstance(df, list):
            return False, "default_fields must be a list of strings"
        unknown = [f for f in df if f not in ALL_WINDOW_FIELDS]
        if unknown:
            return False, f"default_fields contains unknown fields: {unknown}"
        return True, ""

    async def initialize(self) -> None:
        self._detect_backend()
        if self._available:
            backend = self._linux_tool or self._system
            logger.info(f"WindowListTool initialized, backend: {backend}")
        else:
            logger.warning(f"WindowListTool: no backend available on {self._system}")

    async def shutdown(self) -> None:
        logger.info("WindowListTool shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        if not self._available:
            return ToolResult(
                success=False,
                error="Window listing not available on this system",
            )

        if tool_type == TOOL_WINDOWS_LIST:
            return self._do_list_windows(parameters)
        elif tool_type == TOOL_APPS_LIST:
            return self._do_list_apps(parameters)

        return ToolResult(success=False, error=f"Unknown tool: {tool_type}")

    # ------------------------------------------------------------------ #
    # Backend detection                                                    #
    # ------------------------------------------------------------------ #

    def _detect_backend(self) -> None:
        if self._system == PLATFORM_MACOS:
            try:
                import Quartz  # noqa: F401
                self._available = True
            except ImportError:
                logger.warning("WindowListTool: pyobjc-framework-Quartz not installed")

        elif self._system == PLATFORM_WINDOWS:
            try:
                import win32gui  # noqa: F401
                self._available = True
            except ImportError:
                logger.warning("WindowListTool: pywin32 not installed")

        elif self._system == PLATFORM_LINUX:
            linux_cmds = LinuxCommands()
            if shutil.which(linux_cmds.WMCTRL):
                self._linux_tool = linux_cmds.WMCTRL
                self._available = True
            elif shutil.which(linux_cmds.XDOTOOL):
                self._linux_tool = linux_cmds.XDOTOOL
                self._available = True
            else:
                logger.warning("WindowListTool: neither wmctrl nor xdotool found")

    # ------------------------------------------------------------------ #
    # Tool implementations                                                 #
    # ------------------------------------------------------------------ #

    def _do_list_windows(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            only_on_screen = parameters.get("only_on_screen", True)
            include_minimized = parameters.get(
                "include_minimized",
                self.get_config("include_minimized", True),
            )
            app_filter = parameters.get("app_name_filter", "")
            title_filter = parameters.get("title_filter", "")
            fields = self._resolve_fields(parameters)
            max_windows = self.get_config("max_windows", 200)

            windows = self._fetch_windows(only_on_screen, include_minimized)

            if app_filter:
                af = app_filter.lower()
                windows = [w for w in windows if af in w.get("app_name", "").lower()]
            if title_filter:
                tf = title_filter.lower()
                windows = [w for w in windows if tf in w.get("title", "").lower()]

            windows = windows[:max_windows]
            windows = self._filter_fields(windows, fields)

            return ToolResult(
                success=True,
                data={
                    "windows": windows,
                    "count": len(windows),
                    "platform": self._system,
                },
            )
        except Exception as e:
            logger.error(f"WindowListTool list_windows error: {e}")
            return ToolResult(success=False, error=str(e))

    def _do_list_apps(self, parameters: dict[str, Any]) -> ToolResult:
        try:
            include_window_count = parameters.get("include_window_count", True)

            windows = self._fetch_windows(only_on_screen=True, include_minimized=False)

            seen: dict[tuple[str, int], dict[str, Any]] = {}
            for w in windows:
                app_name = w.get("app_name", "")
                pid = w.get("pid", 0)
                key = (app_name, pid)
                if key not in seen:
                    seen[key] = {"app_name": app_name, "pid": pid, "window_count": 0}
                seen[key]["window_count"] += 1

            apps = list(seen.values())

            if not include_window_count:
                for a in apps:
                    a.pop("window_count", None)

            apps.sort(key=lambda a: a.get("app_name", "").lower())

            return ToolResult(
                success=True,
                data={
                    "apps": apps,
                    "count": len(apps),
                    "platform": self._system,
                },
            )
        except Exception as e:
            logger.error(f"WindowListTool list_apps error: {e}")
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------ #
    # Platform-specific window fetchers                                    #
    # ------------------------------------------------------------------ #

    def _fetch_windows(
        self, only_on_screen: bool, include_minimized: bool
    ) -> list[dict[str, Any]]:
        if self._system == PLATFORM_MACOS:
            return self._list_windows_macos(only_on_screen)
        elif self._system == PLATFORM_WINDOWS:
            return self._list_windows_windows(only_on_screen, include_minimized)
        elif self._system == PLATFORM_LINUX:
            return self._list_windows_linux()
        return []

    def _list_windows_macos(self, only_on_screen: bool) -> list[dict[str, Any]]:
        import Quartz

        option = (
            Quartz.kCGWindowListOptionOnScreenOnly
            if only_on_screen
            else Quartz.kCGWindowListOptionAll
        )
        window_list = Quartz.CGWindowListCopyWindowInfo(
            option, Quartz.kCGNullWindowID
        )

        results = []
        for info in window_list or []:
            bounds_raw = info.get("kCGWindowBounds", {})
            results.append({
                "window_id": int(info.get("kCGWindowNumber", 0)),
                "title": info.get("kCGWindowName", "") or "",
                "app_name": info.get("kCGWindowOwnerName", "") or "",
                "pid": int(info.get("kCGWindowOwnerPID", 0)),
                "bounds": {
                    "x": int(bounds_raw.get("X", 0)),
                    "y": int(bounds_raw.get("Y", 0)),
                    "width": int(bounds_raw.get("Width", 0)),
                    "height": int(bounds_raw.get("Height", 0)),
                },
                "is_on_screen": bool(info.get("kCGWindowIsOnscreen", False)),
                "layer": int(info.get("kCGWindowLayer", 0)),
            })
        return results

    def _list_windows_windows(
        self, only_on_screen: bool, include_minimized: bool
    ) -> list[dict[str, Any]]:
        import win32gui
        import win32process

        results: list[dict[str, Any]] = []

        def _callback(hwnd: int, _: Any) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True

            is_minimized = bool(win32gui.IsIconic(hwnd))
            if is_minimized and not include_minimized:
                return True

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                pid = 0

            try:
                rect = win32gui.GetWindowRect(hwnd)
                bounds = {
                    "x": rect[0],
                    "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                }
            except Exception:
                bounds = {"x": 0, "y": 0, "width": 0, "height": 0}

            app_name = _get_process_name_windows(pid)

            results.append({
                "window_id": hwnd,
                "title": title,
                "app_name": app_name,
                "pid": pid,
                "bounds": bounds,
                "is_on_screen": not is_minimized,
                "layer": 0,
            })
            return True

        win32gui.EnumWindows(_callback, None)
        return results

    def _list_windows_linux(self) -> list[dict[str, Any]]:
        linux_cmds = LinuxCommands()
        if self._linux_tool == linux_cmds.WMCTRL:
            return self._list_windows_wmctrl()
        elif self._linux_tool == linux_cmds.XDOTOOL:
            return self._list_windows_xdotool()
        return []

    def _list_windows_wmctrl(self) -> list[dict[str, Any]]:
        try:
            out = subprocess.check_output(
                ["wmctrl", "-lGp"], text=True, timeout=5
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"wmctrl failed: {e}")
            return []

        results = []
        for line in out.strip().splitlines():
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            try:
                window_id = int(parts[0], 16)
                pid = int(parts[2])
                x, y, w, h = int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])
                title = parts[8]
                app_name = self._read_proc_name(pid) or title.rsplit(" - ", 1)[-1]
                results.append({
                    "window_id": window_id,
                    "title": title,
                    "app_name": app_name,
                    "pid": pid,
                    "bounds": {"x": x, "y": y, "width": w, "height": h},
                    "is_on_screen": True,
                    "layer": 0,
                })
            except (ValueError, IndexError):
                continue
        return results

    def _list_windows_xdotool(self) -> list[dict[str, Any]]:
        try:
            ids_out = subprocess.check_output(
                ["xdotool", "search", "--onlyvisible", "--name", ""],
                text=True, timeout=5, stderr=subprocess.DEVNULL,
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"xdotool search failed: {e}")
            return []

        results = []
        for wid_str in ids_out.strip().splitlines():
            try:
                wid = int(wid_str)
            except ValueError:
                continue
            try:
                name_out = subprocess.check_output(
                    ["xdotool", "getwindowname", str(wid)],
                    text=True, timeout=2, stderr=subprocess.DEVNULL,
                )
                title = name_out.strip()
                pid_out = subprocess.check_output(
                    ["xdotool", "getwindowpid", str(wid)],
                    text=True, timeout=2, stderr=subprocess.DEVNULL,
                )
                pid = int(pid_out.strip())
                geom_out = subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", str(wid)],
                    text=True, timeout=2, stderr=subprocess.DEVNULL,
                )
                geom = dict(
                    line.split("=", 1)
                    for line in geom_out.strip().splitlines()
                    if "=" in line
                )
                bounds = {
                    "x": int(geom.get("X", 0)),
                    "y": int(geom.get("Y", 0)),
                    "width": int(geom.get("WIDTH", 0)),
                    "height": int(geom.get("HEIGHT", 0)),
                }
                app_name = self._read_proc_name(pid) or title
                results.append({
                    "window_id": wid,
                    "title": title,
                    "app_name": app_name,
                    "pid": pid,
                    "bounds": bounds,
                    "is_on_screen": True,
                    "layer": 0,
                })
            except (subprocess.SubprocessError, ValueError):
                continue
        return results

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _resolve_fields(self, parameters: dict[str, Any]) -> list[str]:
        raw = parameters.get("fields", self.get_config("default_fields", DEFAULT_FIELDS))
        if isinstance(raw, list):
            valid = [f for f in raw if f in ALL_WINDOW_FIELDS]
            return valid if valid else DEFAULT_FIELDS
        return DEFAULT_FIELDS

    def _filter_fields(
        self, items: list[dict[str, Any]], fields: list[str]
    ) -> list[dict[str, Any]]:
        return [{k: v for k, v in item.items() if k in fields} for item in items]

    @staticmethod
    def _read_proc_name(pid: int) -> str:
        """Read process name from /proc on Linux. Returns empty string on failure."""
        if pid <= 0:
            return ""
        try:
            return Path(f"/proc/{pid}/comm").read_text().strip()
        except Exception:
            return ""


def _get_process_name_windows(pid: int) -> str:
    """Best-effort process name lookup on Windows."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.name().rsplit(".", 1)[0]
    except Exception:
        return ""
