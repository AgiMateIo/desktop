# Plugin Development Guide

This guide explains how to create new plugins for System Agent.

## Table of Contents

- [Plugin Architecture](#plugin-architecture)
- [Plugin Types](#plugin-types)
- [Creating a Trigger Plugin](#creating-a-trigger-plugin)
- [Creating an Action Plugin](#creating-an-action-plugin)
- [Plugin Configuration](#plugin-configuration)
- [Config Validation](#config-validation)
- [Plugin UI](#plugin-ui)
- [Testing Plugins](#testing-plugins)
- [Best Practices](#best-practices)

## Plugin Architecture

Plugins are dynamically loaded Python modules that extend System Agent functionality:

```
plugins/
├── triggers/           # Plugins that detect events
│   └── my_trigger/
│       ├── __init__.py
│       ├── plugin.py   # Main plugin class
│       └── config.json # Plugin configuration
└── actions/            # Plugins that perform actions
    └── my_action/
        ├── __init__.py
        ├── plugin.py
        └── config.json
```

### Plugin Lifecycle

1. **Discovery** - Plugin Manager scans `plugins/` directory
2. **Load** - Imports `plugin.py` from each plugin directory
3. **Initialize** - Calls `plugin.initialize()` for setup
4. **Run** - Triggers start monitoring, actions wait for execution
5. **Shutdown** - Calls `plugin.shutdown()` for cleanup

### Event Flow

```
Trigger Plugin → emit_event() → PluginManager → EventBus → Application → ServerClient → Server
                                                                                            ↓
Server → WebSocket → ServerClient → EventBus → Application → PluginManager → Action Plugin
```

## Plugin Types

### Trigger Plugins

**Purpose:** Detect events and send them to the server

**Examples:**
- File Watcher - monitors directory for file changes
- Visual Buttons - manual trigger buttons with UI
- Timer - periodic triggers
- System Event - CPU/memory thresholds

**Base Class:** `TriggerPlugin`

### Action Plugins

**Purpose:** Execute actions requested by the server

**Examples:**
- Show Notification - display system notifications
- TTS - text-to-speech
- Run Command - execute shell commands
- Send Keys - simulate keyboard input

**Base Class:** `ActionPlugin`

## Creating a Trigger Plugin

### 1. Create Plugin Directory

```bash
mkdir -p plugins/triggers/my_trigger
cd plugins/triggers/my_trigger
```

### 2. Create `__init__.py`

```python
"""My Trigger plugin."""

from .plugin import MyTriggerPlugin
```

### 3. Create `plugin.py`

```python
"""My Trigger plugin implementation."""

import logging
from pathlib import Path

from core.plugin_base import TriggerPlugin

logger = logging.getLogger(__name__)


class MyTriggerPlugin(TriggerPlugin):
    """Trigger plugin that detects custom events."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._monitoring_task = None

    @property
    def name(self) -> str:
        """Plugin name shown in UI."""
        return "My Trigger"

    async def initialize(self) -> None:
        """Initialize plugin resources."""
        logger.info(f"{self.name} initialized")
        # Load config, setup resources
        self.my_setting = self.get_config("my_setting", "default_value")

    async def start(self) -> None:
        """Start monitoring for events."""
        self._running = True
        logger.info(f"{self.name} started")

        # Start your monitoring logic
        import asyncio
        self._monitoring_task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

        # Cancel monitoring task
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info(f"{self.name} stopped")

    async def shutdown(self) -> None:
        """Cleanup plugin resources."""
        await self.stop()
        logger.info(f"{self.name} shutdown")

    async def _monitor(self) -> None:
        """Main monitoring loop."""
        while self._running:
            # Your monitoring logic here

            # When event detected, emit it:
            event_detected = await self._check_for_event()
            if event_detected:
                self.emit_event(
                    "device.my_trigger.detected",
                    {"detail": "event details"}
                )

            await asyncio.sleep(1)  # Adjust interval as needed

    async def _check_for_event(self) -> bool:
        """Check if event occurred."""
        # Your detection logic
        return False
```

### 4. Create `config.json`

```json
{
  "enabled": true,
  "my_setting": "default_value",
  "check_interval": 5
}
```

### 5. Optional: Add Plugin Window

```python
class MyTriggerPlugin(TriggerPlugin):
    # ... previous methods ...

    def has_window(self) -> bool:
        """This plugin has a UI window."""
        return True

    def create_window(self, parent=None):
        """Create plugin window."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

        class MyPluginWindow(QDialog):
            def __init__(self, plugin, parent=None):
                super().__init__(parent)
                self.plugin = plugin
                self.setWindowTitle("My Trigger")

                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(f"Status: {'Running' if plugin._running else 'Stopped'}"))

        return MyPluginWindow(self, parent)
```

### 6. Optional: Add Tray Menu Item

```python
def get_tray_menu_item(self, on_click: Callable | None = None) -> TrayMenuItem | None:
    """Add custom menu item."""
    from core.plugin_base import TrayMenuItem

    return TrayMenuItem(
        label=f"{self.name}: {self.status_text}",
        callback=lambda: on_click(self) if on_click else None,
        enabled=self.enabled
    )
```

## Creating an Action Plugin

### 1. Create Plugin Directory

```bash
mkdir -p plugins/actions/my_action
cd plugins/actions/my_action
```

### 2. Create `__init__.py`

```python
"""My Action plugin."""

from .plugin import MyActionPlugin
```

### 3. Create `plugin.py`

```python
"""My Action plugin implementation."""

import logging
from pathlib import Path

from core.plugin_base import ActionPlugin

logger = logging.getLogger(__name__)


class MyActionPlugin(ActionPlugin):
    """Action plugin that performs custom actions."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)

    @property
    def name(self) -> str:
        """Plugin name shown in UI."""
        return "My Action"

    def get_supported_actions(self) -> list[str]:
        """Return list of action types this plugin handles."""
        return ["MY_CUSTOM_ACTION", "MY_OTHER_ACTION"]

    async def initialize(self) -> None:
        """Initialize plugin resources."""
        logger.info(f"{self.name} initialized")
        # Setup resources
        self.my_setting = self.get_config("my_setting", "default")

    async def shutdown(self) -> None:
        """Cleanup plugin resources."""
        logger.info(f"{self.name} shutdown")

    async def execute(self, action_type: str, parameters: dict) -> bool:
        """Execute the requested action.

        Args:
            action_type: One of the supported action types
            parameters: Action parameters from server

        Returns:
            True if action succeeded, False otherwise
        """
        try:
            if action_type == "MY_CUSTOM_ACTION":
                return await self._handle_custom_action(parameters)
            elif action_type == "MY_OTHER_ACTION":
                return await self._handle_other_action(parameters)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return False
        except Exception as e:
            logger.error(f"Error executing {action_type}: {e}")
            return False

    async def _handle_custom_action(self, params: dict) -> bool:
        """Handle MY_CUSTOM_ACTION."""
        message = params.get("message", "No message")
        logger.info(f"Executing custom action: {message}")

        # Your action logic here

        return True

    async def _handle_other_action(self, params: dict) -> bool:
        """Handle MY_OTHER_ACTION."""
        value = params.get("value", 0)
        logger.info(f"Executing other action: {value}")

        # Your action logic here

        return True
```

### 4. Create `config.json`

```json
{
  "enabled": true,
  "my_setting": "default"
}
```

## Plugin Configuration

### Config File Format

Each plugin has a `config.json` file in its directory:

```json
{
  "enabled": true,        // Required: plugin enabled/disabled
  "custom_setting": 42,   // Your custom settings
  "api_key": "secret"     // Plugin-specific config
}
```

### Reading Config

```python
# In your plugin
value = self.get_config("custom_setting", default_value)

# Or access _config directly
all_config = self._config
```

### Updating Config

```python
# Update config
self._config["custom_setting"] = new_value

# Save to disk
self.save_config()
```

### Config Schema

You can document your config schema in docstring:

```python
class MyPlugin(TriggerPlugin):
    """My plugin.

    Config Schema:
        enabled (bool): Enable/disable plugin
        check_interval (int): Check interval in seconds (default: 5)
        api_key (str): API key for service
        max_retries (int): Maximum retry attempts (default: 3)
    """
```

## Config Validation

Override `validate_config()` to validate configuration:

```python
def validate_config(self) -> tuple[bool, str]:
    """Validate plugin configuration.

    Returns:
        (valid, error_message) tuple
    """
    # Validate required fields
    api_key = self._config.get("api_key")
    if not api_key:
        return False, "api_key is required"

    # Validate types
    check_interval = self._config.get("check_interval", 5)
    if not isinstance(check_interval, int):
        return False, "check_interval must be an integer"

    # Validate ranges
    if check_interval <= 0:
        return False, "check_interval must be positive"
    if check_interval > 3600:
        return False, "check_interval must be ≤ 3600 seconds"

    # Validate choices
    mode = self._config.get("mode", "auto")
    if mode not in ("auto", "manual"):
        return False, f"mode must be 'auto' or 'manual', got '{mode}'"

    return True, ""
```

**What happens on validation failure:**
- Plugin is automatically disabled (`enabled: false`)
- Error message logged
- Plugin shown as failed in UI
- User must fix config and restart

## Plugin UI

### Window-Based UI

For trigger plugins that need user interaction:

```python
def has_window(self) -> bool:
    return True

def create_window(self, parent=None):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton

    class MyPluginWindow(QDialog):
        def __init__(self, plugin, parent=None):
            super().__init__(parent)
            self.plugin = plugin

            self.setWindowTitle(plugin.name)
            self.setMinimumSize(400, 300)

            layout = QVBoxLayout(self)

            # Add your UI widgets
            button = QPushButton("Trigger Event")
            button.clicked.connect(self._on_button_click)
            layout.addWidget(button)

        def _on_button_click(self):
            self.plugin.emit_event("device.button.clicked", {})

    return MyPluginWindow(self, parent)
```

### Tray Menu Integration

Add custom menu item to system tray:

```python
def get_tray_menu_item(self, on_click: Callable | None = None) -> TrayMenuItem | None:
    from core.plugin_base import TrayMenuItem

    # Simple menu item
    return TrayMenuItem(
        label=f"{self.name}: {self._get_status()}",
        callback=lambda: on_click(self) if on_click else None,
        enabled=self.enabled
    )

    # Or submenu with multiple items
    return TrayMenuItem(
        label=self.name,
        children=[
            TrayMenuItem(label="Start", callback=lambda: self._start_action()),
            TrayMenuItem(label="Stop", callback=lambda: self._stop_action()),
            TrayMenuItem(label="Settings", callback=lambda: on_click(self)),
        ],
        separator_after=True
    )
```

## Testing Plugins

### Unit Tests

Create `test_plugin.py` in your plugin directory:

```python
"""Tests for My Trigger plugin."""

import pytest
from pathlib import Path
from .plugin import MyTriggerPlugin


class TestMyTriggerPlugin:
    """Tests for MyTriggerPlugin."""

    def test_plugin_name(self, tmp_path):
        plugin = MyTriggerPlugin(tmp_path)
        assert plugin.name == "My Trigger"

    @pytest.mark.asyncio
    async def test_initialize(self, tmp_path):
        plugin = MyTriggerPlugin(tmp_path)
        await plugin.initialize()
        # Assert initialization worked

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        plugin = MyTriggerPlugin(tmp_path)
        await plugin.initialize()

        await plugin.start()
        assert plugin._running

        await plugin.stop()
        assert not plugin._running
```

### Manual Testing

```bash
# Test your plugin
python main.py

# Check logs
tail -f ~/.config/systemagent/logs/system_agent.log

# Test with different configs
# Edit plugins/triggers/my_trigger/config.json
# Restart application
```

## Best Practices

### DO ✅

1. **Use async/await** - All plugin methods should be async-compatible
2. **Handle errors gracefully** - Don't crash the entire application
3. **Log important events** - Use Python logging module
4. **Validate config** - Implement `validate_config()` for robustness
5. **Clean up resources** - Cancel tasks in `shutdown()`
6. **Use type hints** - Makes code maintainable
7. **Document config schema** - In class docstring
8. **Test your plugin** - Write unit tests

### DON'T ❌

1. **Don't block the event loop** - Use `asyncio.sleep()`, not `time.sleep()`
2. **Don't ignore exceptions** - Log and handle errors properly
3. **Don't hardcode paths** - Use `self.plugin_dir` or `core.paths`
4. **Don't store secrets in code** - Use config.json or environment vars
5. **Don't modify other plugins** - Plugins should be independent
6. **Don't leak resources** - Close files, connections, etc.
7. **Don't use global state** - Keep state in plugin instance
8. **Don't skip validation** - Always validate user inputs

### Code Style

```python
# Good: Clear, async, error handling
@property
def name(self) -> str:
    return "My Plugin"

async def start(self) -> None:
    """Start monitoring."""
    try:
        self._running = True
        self._task = asyncio.create_task(self._monitor())
        logger.info(f"{self.name} started")
    except Exception as e:
        logger.error(f"Failed to start {self.name}: {e}")
        raise

# Bad: No types, blocking, no error handling
def start(self):
    self._running = True
    time.sleep(1)  # WRONG: blocks event loop
    self._monitor()  # WRONG: not awaited
```

### Performance Tips

1. **Use appropriate intervals** - Don't poll too frequently
2. **Batch operations** - Process multiple events together
3. **Cache when possible** - Avoid redundant calculations
4. **Use asyncio primitives** - `asyncio.Queue`, `asyncio.Event`, etc.
5. **Limit resource usage** - Memory, CPU, file handles

### Security Considerations

1. **Validate all inputs** - From config and server
2. **Sanitize shell commands** - Use subprocess securely
3. **Don't eval/exec user input** - Huge security risk
4. **Limit file system access** - Don't access arbitrary paths
5. **Use secure connections** - HTTPS for API calls

## Examples

See existing plugins for complete examples:

- **Simple Trigger**: `plugins/triggers/file_watcher/` - Monitors directory
- **UI Trigger**: `plugins/triggers/visual_buttons/` - Button grid with dialogs
- **Simple Action**: `plugins/actions/show_notification/` - Shows notifications
- **Complex Action**: `plugins/actions/tts/` - Platform-specific TTS

## Plugin Checklist

Before submitting a plugin:

- [ ] Plugin has meaningful name
- [ ] `__init__.py` exports plugin class
- [ ] `config.json` has valid structure
- [ ] `validate_config()` implemented
- [ ] Proper error handling
- [ ] Resources cleaned up in `shutdown()`
- [ ] Logging added for debugging
- [ ] Type hints on all methods
- [ ] Docstrings on class and methods
- [ ] Unit tests written
- [ ] Tested manually
- [ ] README with usage instructions

## Getting Help

- Read existing plugin code
- Check `core/plugin_base.py` for base classes
- Look at test files for examples
- Ask in project issues

Happy plugin development! 🚀
