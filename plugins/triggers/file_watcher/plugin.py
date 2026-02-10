"""File Watcher trigger plugin implementation."""

import asyncio
import fnmatch
import logging
import os
from pathlib import Path
from typing import Any

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)

from core.plugin_base import TriggerPlugin, TrayMenuItem

logger = logging.getLogger(__name__)


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events and forwards them to the plugin."""

    def __init__(
        self,
        plugin: "FileWatcherTrigger",
        watch_path: str,
        patterns: list[str],
        events: list[str],
    ):
        super().__init__()
        self.plugin = plugin
        self.watch_path = watch_path
        self.patterns = patterns
        self.events = events

    def _matches_patterns(self, filename: str) -> bool:
        """Check if filename matches any of the configured patterns."""
        if not self.patterns:
            return True
        return any(fnmatch.fnmatch(filename, pattern) for pattern in self.patterns)

    def _should_handle_event(self, event_type: str) -> bool:
        """Check if this event type should be handled."""
        if not self.events:
            return True
        return event_type in self.events

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        if not self._should_handle_event("created"):
            return

        filename = os.path.basename(event.src_path)
        if self._matches_patterns(filename):
            self.plugin.emit_file_event("created", event.src_path, self.watch_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        if not self._should_handle_event("modified"):
            return

        filename = os.path.basename(event.src_path)
        if self._matches_patterns(filename):
            self.plugin.emit_file_event("modified", event.src_path, self.watch_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if event.is_directory:
            return
        if not self._should_handle_event("deleted"):
            return

        filename = os.path.basename(event.src_path)
        if self._matches_patterns(filename):
            self.plugin.emit_file_event("deleted", event.src_path, self.watch_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if event.is_directory:
            return
        if not self._should_handle_event("moved"):
            return

        filename = os.path.basename(event.dest_path)
        if self._matches_patterns(filename):
            self.plugin.emit_file_event(
                "moved",
                event.dest_path,
                self.watch_path,
                {"src_path": event.src_path}
            )


class FileWatcherTrigger(TriggerPlugin):
    """Trigger plugin for monitoring file system changes."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def name(self) -> str:
        return "File Watcher"

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self._loop = asyncio.get_event_loop()
        logger.info("FileWatcherTrigger initialized")

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        await self.stop()
        logger.info("FileWatcherTrigger shutdown")

    async def start(self) -> None:
        """Start watching configured directories."""
        if self._running:
            return

        watch_paths = self.get_config("watch_paths", [])
        if not watch_paths:
            logger.warning("No watch paths configured for FileWatcherTrigger")
            return

        self._observer = Observer()

        for wp in watch_paths:
            path = os.path.expanduser(wp.get("path", ""))
            if not path or not os.path.exists(path):
                logger.warning(f"Watch path does not exist: {path}")
                continue

            patterns = wp.get("patterns", [])
            recursive = wp.get("recursive", False)
            events = wp.get("events", ["created"])

            handler = FileEventHandler(self, path, patterns, events)
            self._observer.schedule(handler, path, recursive=recursive)
            logger.info(f"Watching: {path} (patterns: {patterns}, recursive: {recursive})")

        self._observer.start()
        self._running = True
        logger.info("FileWatcherTrigger started")

    async def stop(self) -> None:
        """Stop watching directories."""
        if not self._running or self._observer is None:
            return

        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._running = False
        logger.info("FileWatcherTrigger stopped")

    def get_capabilities(self) -> dict[str, list[str]]:
        """Return file watcher trigger capabilities."""
        common = ["path", "filename", "watch_path", "event_type", "size"]
        return {
            "desktop.trigger.filewatcher.created": common,
            "desktop.trigger.filewatcher.modified": common,
            "desktop.trigger.filewatcher.deleted": common,
            "desktop.trigger.filewatcher.moved": common + ["src_path"],
        }

    def emit_file_event(
        self,
        event_type: str,
        file_path: str,
        watch_path: str,
        extra_data: dict[str, Any] | None = None
    ) -> None:
        """Emit a file event."""
        data = {
            "path": file_path,
            "filename": os.path.basename(file_path),
            "watch_path": watch_path,
            "event_type": event_type,
        }

        try:
            data["size"] = os.path.getsize(file_path)
        except (OSError, FileNotFoundError):
            data["size"] = 0

        if extra_data:
            data.update(extra_data)

        event_name = f"desktop.trigger.filewatcher.{event_type}"

        # Emit event in the main thread if we have a loop
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: self.emit_event(event_name, data)
            )
        else:
            self.emit_event(event_name, data)

        logger.info(f"File event: {event_name} - {file_path}")

    def get_tray_menu_items(self) -> list[TrayMenuItem]:
        """Return menu items for the tray."""
        return [
            TrayMenuItem(
                id="file_watcher_status",
                label=f"File Watcher: {'Running' if self._running else 'Stopped'}",
                callback=None
            )
        ]
