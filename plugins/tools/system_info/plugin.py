"""System Info tool plugin."""

import logging
from pathlib import Path
from typing import Any

from core.plugin_base import ToolPlugin
from core.models import ToolResult
from core.tool_types import TOOL_SYSINFO_SNAPSHOT, TOOL_SYSINFO_SCREENS

logger = logging.getLogger(__name__)

ALL_SECTIONS = ["os", "cpu", "memory", "disks", "network", "uptime", "screens"]


class SystemInfoTool(ToolPlugin):
    """Tool plugin for gathering system information."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._psutil_available = False
        self._qt_available = False

    @property
    def name(self) -> str:
        return "System Info"

    @property
    def description(self) -> str:
        return "Collects OS, CPU, memory, disk, network, uptime, and screen information"

    @property
    def status(self) -> str:
        if not self.enabled:
            return "Disabled"
        if not self._psutil_available:
            return "psutil not installed"
        return "Running"

    def get_supported_tools(self) -> list[str]:
        return [TOOL_SYSINFO_SNAPSHOT, TOOL_SYSINFO_SCREENS]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            TOOL_SYSINFO_SNAPSHOT: {
                "params": ["sections"],
                "description": (
                    "Return a full system snapshot. "
                    "Optional 'sections' list filters output to specific keys: "
                    f"{ALL_SECTIONS}. "
                    "Omit to receive all sections."
                ),
            },
            TOOL_SYSINFO_SCREENS: {
                "params": [],
                "description": (
                    "Return display/screen information: "
                    "resolution, DPI, refresh rate, device pixel ratio, geometry, and name."
                ),
            },
        }

    async def initialize(self) -> None:
        try:
            import psutil  # noqa: F401
            self._psutil_available = True
            logger.info("SystemInfoTool initialized with psutil")
        except ImportError:
            logger.error(
                "SystemInfoTool: psutil not installed — install via: pip install psutil"
            )

        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is not None:
                self._qt_available = True
        except Exception as e:
            logger.warning(f"SystemInfoTool: Qt unavailable for screen info: {e}")

    async def shutdown(self) -> None:
        logger.info("SystemInfoTool shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        if tool_type == TOOL_SYSINFO_SNAPSHOT:
            return self._snapshot(parameters)
        elif tool_type == TOOL_SYSINFO_SCREENS:
            return self._screens()

        return ToolResult(success=False, error=f"Unknown tool: {tool_type}")

    def _snapshot(self, parameters: dict[str, Any]) -> ToolResult:
        if not self._psutil_available:
            return ToolResult(success=False, error="psutil not available")

        requested = parameters.get("sections")
        if requested is not None and not isinstance(requested, list):
            return ToolResult(
                success=False, error="'sections' must be a list of strings"
            )

        from .collectors.os_info import collect_os_info
        from .collectors.cpu_info import collect_cpu_info
        from .collectors.memory_info import collect_memory_info
        from .collectors.disk_info import collect_disk_info
        from .collectors.network_info import collect_network_info
        from .collectors.uptime_info import collect_uptime_info
        from .collectors.screen_info import collect_screen_info

        all_collectors = {
            "os": collect_os_info,
            "cpu": collect_cpu_info,
            "memory": collect_memory_info,
            "disks": collect_disk_info,
            "network": collect_network_info,
            "uptime": collect_uptime_info,
            "screens": lambda: collect_screen_info(self._qt_available),
        }

        target = requested if requested else list(all_collectors.keys())
        data: dict[str, Any] = {}
        errors: dict[str, str] = {}

        for section in target:
            if section not in all_collectors:
                errors[section] = f"Unknown section '{section}'"
                continue
            try:
                data[section] = all_collectors[section]()
            except Exception as e:
                logger.error(f"SystemInfoTool: error collecting '{section}': {e}")
                errors[section] = str(e)

        if errors:
            data["_errors"] = errors

        # If no actual data was collected, report failure
        data_sections = {k: v for k, v in data.items() if k != "_errors"}
        if not data_sections and errors:
            return ToolResult(
                success=False, error=f"All sections failed: {errors}"
            )

        return ToolResult(success=True, data=data)

    def _screens(self) -> ToolResult:
        if not self._qt_available:
            return ToolResult(
                success=False, error="Qt not available for screen info"
            )

        from .collectors.screen_info import collect_screen_info

        try:
            screens = collect_screen_info(self._qt_available)
            return ToolResult(success=True, data={"screens": screens})
        except Exception as e:
            logger.error(f"SystemInfoTool: screen collection error: {e}")
            return ToolResult(success=False, error=str(e))
