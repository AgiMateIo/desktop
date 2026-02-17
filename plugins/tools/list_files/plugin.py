"""List Files tool plugin implementation."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.plugin_base import ToolPlugin
from core.tool_types import TOOL_FILES_LIST
from core.models import ToolResult

logger = logging.getLogger(__name__)


class ListFilesTool(ToolPlugin):
    """Tool plugin for listing files in a configured directory."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)

    @property
    def name(self) -> str:
        return "List Files"

    @property
    def description(self) -> str:
        return "Lists files in a configured directory with name, size, and dates"

    def get_supported_tools(self) -> list[str]:
        return [TOOL_FILES_LIST]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        return {
            TOOL_FILES_LIST: {
                "params": ["directory"],
                "description": "List files with name, size, created and modified dates",
            },
        }

    def validate_config(self) -> tuple[bool, str]:
        target = self._config.get("target_directory", "")
        if not target:
            return False, "target_directory must not be empty"
        return True, ""

    async def initialize(self) -> None:
        logger.info("ListFilesTool initialized")

    async def shutdown(self) -> None:
        logger.info("ListFilesTool shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        if tool_type != TOOL_FILES_LIST:
            return ToolResult(success=False, error=f"Unsupported tool: {tool_type}")

        configured_base = Path(self.get_config("target_directory")).expanduser().resolve()
        requested_dir = parameters.get("directory")

        if requested_dir:
            target_path = Path(requested_dir).expanduser().resolve()
            # Prevent path traversal outside the configured base
            if not str(target_path).startswith(str(configured_base)):
                return ToolResult(success=False, error="Access denied: directory outside configured base")
        else:
            target_path = configured_base

        if not target_path.exists():
            return ToolResult(success=False, error=f"Directory not found: {target_path}")

        if not target_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {target_path}")

        try:
            files = []
            for entry in target_path.iterdir():
                try:
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "size": stat.st_size,
                        "is_dir": entry.is_dir(),
                        "created_at": datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc).isoformat()
                        if hasattr(stat, "st_birthtime")
                        else datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    })
                except OSError as e:
                    logger.warning(f"Cannot stat {entry}: {e}")

            files.sort(key=lambda f: f["modified_at"], reverse=True)

            return ToolResult(
                success=True,
                data={
                    "directory": str(target_path),
                    "count": len(files),
                    "files": files,
                },
            )
        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {target_path}")
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return ToolResult(success=False, error=str(e))
