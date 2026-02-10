"""Tests for file_watcher trigger plugin."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileDeletedEvent, FileMovedEvent

from .plugin import FileWatcherTrigger


class TestFileWatcherInit:
    """Test cases for FileWatcherTrigger initialization."""

    def test_init(self, tmp_path):
        """Test FileWatcherTrigger initialization."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        assert plugin.plugin_dir == plugin_dir
        assert plugin.plugin_id == "file_watcher"
        assert plugin.name == "File Watcher"
        assert plugin._observer is None
        assert plugin._loop is None

    def test_load_config(self, tmp_path):
        """Test loading plugin configuration."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        # Create config with watch paths
        config = {
            "enabled": True,
            "watch_paths": [
                {
                    "path": str(tmp_path / "watched"),
                    "patterns": ["*.txt", "*.log"],
                    "events": ["created", "modified"]
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()

        assert plugin.enabled is True
        assert len(plugin.get_config("watch_paths")) == 1
        assert plugin.get_config("watch_paths")[0]["path"] == str(tmp_path / "watched")


class TestFileWatcherLifecycle:
    """Test cases for plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize(self, tmp_path):
        """Test initialize() method."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        await plugin.initialize()

        # Should not crash
        assert plugin._observer is None  # Not started yet

    @pytest.mark.asyncio
    async def test_shutdown(self, tmp_path):
        """Test shutdown() method."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        await plugin.initialize()
        await plugin.shutdown()

        # Should not crash
        assert plugin._observer is None

    @pytest.mark.asyncio
    async def test_start_creates_observer(self, tmp_path):
        """Test start() creates watchdog observer."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        # Create watched directory
        watched_dir = tmp_path / "watched"
        watched_dir.mkdir()

        # Create config
        config = {
            "enabled": True,
            "watch_paths": [
                {
                    "path": str(watched_dir),
                    "patterns": ["*.txt"],
                    "events": ["created"]
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()
        await plugin.initialize()

        with patch('plugins.triggers.file_watcher.plugin.Observer') as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer

            await plugin.start()

            assert plugin.running is True
            assert plugin._observer is not None
            mock_observer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stops_observer(self, tmp_path):
        """Test stop() stops watchdog observer."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        watched_dir = tmp_path / "watched"
        watched_dir.mkdir()

        config = {
            "enabled": True,
            "watch_paths": [
                {
                    "path": str(watched_dir),
                    "patterns": ["*.txt"],
                    "events": ["created"]
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()
        await plugin.initialize()

        with patch('plugins.triggers.file_watcher.plugin.Observer') as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer

            await plugin.start()
            await plugin.stop()

            assert plugin.running is False
            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_without_watch_paths(self, tmp_path):
        """Test start() with no watch paths configured."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)
        await plugin.initialize()

        # Should not crash
        await plugin.start()

        # Should not create observer
        assert plugin._observer is None


class TestEventEmission:
    """Test cases for file event emission."""

    def test_emit_file_event(self, tmp_path):
        """Test emit_file_event() emits correct event."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))

        # Mock loop for thread-safe call
        plugin._loop = Mock()
        plugin._loop.call_soon_threadsafe = lambda fn: fn()

        # Emit event
        plugin.emit_file_event(
            "created",
            "/path/to/test.txt",
            "/path/to",
            {"size": 1024}
        )

        assert len(events_received) == 1
        event = events_received[0]
        assert event.event_name == "desktop.trigger.filewatcher.created"
        assert event.data["path"] == "/path/to/test.txt"
        assert event.data["filename"] == "test.txt"
        assert event.data["watch_path"] == "/path/to"
        assert event.data["size"] == 1024

    def test_emit_file_event_different_types(self, tmp_path):
        """Test emit_file_event() with different event types."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)
        plugin._loop = Mock()
        plugin._loop.call_soon_threadsafe = lambda fn: fn()

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))

        # Test different event types
        event_types = ["created", "modified", "deleted", "moved"]
        for event_type in event_types:
            plugin.emit_file_event(event_type, f"/path/test.txt", "/path", {})

        assert len(events_received) == 4
        assert events_received[0].event_name == "desktop.trigger.filewatcher.created"
        assert events_received[1].event_name == "desktop.trigger.filewatcher.modified"
        assert events_received[2].event_name == "desktop.trigger.filewatcher.deleted"
        assert events_received[3].event_name == "desktop.trigger.filewatcher.moved"


class TestPatternMatching:
    """Test cases for file pattern matching."""

    def test_matches_patterns_simple(self, tmp_path):
        """Test _matches_patterns() with simple patterns."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        from plugins.triggers.file_watcher.plugin import FileEventHandler

        # Test *.txt pattern
        handler = FileEventHandler(plugin, "/path", ["*.txt"], [])
        assert handler._matches_patterns("test.txt") is True
        assert handler._matches_patterns("test.log") is False

        # Test *.log pattern
        handler = FileEventHandler(plugin, "/path", ["*.log"], [])
        assert handler._matches_patterns("app.log") is True

    def test_matches_patterns_multiple(self, tmp_path):
        """Test _matches_patterns() with multiple patterns."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        from plugins.triggers.file_watcher.plugin import FileEventHandler

        patterns = ["*.txt", "*.log", "*.json"]
        handler = FileEventHandler(plugin, "/path", patterns, [])

        assert handler._matches_patterns("test.txt") is True
        assert handler._matches_patterns("test.log") is True
        assert handler._matches_patterns("config.json") is True
        assert handler._matches_patterns("image.png") is False

    def test_matches_patterns_no_patterns(self, tmp_path):
        """Test _matches_patterns() with no patterns (match all)."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        from plugins.triggers.file_watcher.plugin import FileEventHandler

        # Empty patterns should match all
        handler = FileEventHandler(plugin, "/path", [], [])
        assert handler._matches_patterns("test.txt") is True
        assert handler._matches_patterns("anything") is True


class TestEventHandlerIntegration:
    """Integration tests for file event handler."""

    @pytest.mark.asyncio
    async def test_file_created_event_flow(self, tmp_path):
        """Test complete flow for file created event."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        watched_dir = tmp_path / "watched"
        watched_dir.mkdir()

        config = {
            "enabled": True,
            "watch_paths": [
                {
                    "path": str(watched_dir),
                    "patterns": ["*.txt"],
                    "events": ["created"]
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()

        events_received = []
        plugin.on_event(lambda e: events_received.append(e))

        await plugin.initialize()

        # Mock loop
        plugin._loop = Mock()
        plugin._loop.call_soon_threadsafe = lambda fn: fn()

        # Simulate file created event
        test_file = watched_dir / "test.txt"
        event = FileCreatedEvent(str(test_file))

        # Get the event handler
        with patch('plugins.triggers.file_watcher.plugin.Observer'):
            await plugin.start()

            # Manually trigger the event handler
            if plugin._observer:
                handler = plugin._observer._emitters[0]._watch._event_handler
                handler.on_created(event)

    def test_should_handle_event(self, tmp_path):
        """Test _should_handle_event() method."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)

        from plugins.triggers.file_watcher.plugin import FileEventHandler

        # Test matching event types
        handler = FileEventHandler(plugin, "/path", [], ["created", "modified"])
        assert handler._should_handle_event("created") is True
        assert handler._should_handle_event("modified") is True
        assert handler._should_handle_event("deleted") is False

        # Empty event types should match all
        handler2 = FileEventHandler(plugin, "/path", [], [])
        assert handler2._should_handle_event("created") is True
        assert handler2._should_handle_event("deleted") is True


class TestConfiguration:
    """Test cases for plugin configuration."""

    def test_default_config(self, tmp_path):
        """Test plugin with default empty config."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()

        # Should have default values
        watch_paths = plugin.get_config("watch_paths", [])
        assert watch_paths == []

    def test_multiple_watch_paths(self, tmp_path):
        """Test configuration with multiple watch paths."""
        plugin_dir = tmp_path / "file_watcher"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "watch_paths": [
                {
                    "path": "/path/one",
                    "patterns": ["*.txt"],
                    "events": ["created"]
                },
                {
                    "path": "/path/two",
                    "patterns": ["*.log"],
                    "events": ["modified", "deleted"]
                }
            ]
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        plugin = FileWatcherTrigger(plugin_dir)
        plugin.load_config()

        watch_paths = plugin.get_config("watch_paths")
        assert len(watch_paths) == 2
        assert watch_paths[0]["path"] == "/path/one"
        assert watch_paths[1]["path"] == "/path/two"
