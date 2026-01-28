# Agimate Desktop

Cross-platform system tray agent with plugin architecture for triggers and actions.

## Project Structure

```
agimate-desktop/
├── main.py                 # Entry point with DI architecture
├── build.py                # Build script for PyInstaller
├── agimate_desktop.spec    # PyInstaller configuration
├── requirements.txt        # Dependencies
├── core/
│   ├── application.py      # Application coordinator (replaces old SystemAgent)
│   ├── di_container.py     # Dependency injection container
│   ├── event_bus.py        # EventBus for pub/sub communication
│   ├── protocols.py        # Protocol interfaces for DI
│   ├── plugin_base.py      # Base classes: TriggerPlugin, ActionPlugin
│   ├── plugin_manager.py   # Plugin discovery and lifecycle
│   ├── config_manager.py   # App configuration
│   ├── device_info.py      # Device ID and platform info
│   ├── server_client.py    # HTTP + WebSocket/Centrifugo client
│   ├── retry.py            # Retry logic with exponential backoff
│   ├── models.py           # TriggerPayload, ActionTask
│   ├── constants.py        # Application constants
│   ├── api_endpoints.py    # API endpoint constants
│   ├── action_types.py     # Action type constants
│   ├── platform_commands.py # Platform-specific command constants
│   └── paths.py            # Path utilities for bundled app support
├── ui/
│   ├── tray.py             # System tray with notifications
│   └── settings.py         # Settings window (General, Plugins, Device)
├── plugins/
│   ├── triggers/
│   │   ├── file_watcher/   # Watches directory for file changes
│   │   └── visual_buttons/ # Manual trigger buttons with UI window
│   └── actions/
│       ├── show_notification/  # Cross-platform notifications
│       └── tts/            # Text-to-speech using system tools
├── tests/                  # Comprehensive test suite (313 tests)
└── assets/                 # Icons and resources
```

## Tech Stack

- **Python 3.11+**
- **PySide6** — Qt GUI and system tray
- **qasync** — asyncio + Qt event loop integration
- **aiohttp** — HTTP client for triggers
- **centrifuge-python** (v0.4.x) — Centrifugo WebSocket client
- **watchdog** — File system monitoring
- **PyInstaller** — Application packaging

## Architecture

The application uses **Dependency Injection** and **EventBus** for clean, decoupled architecture.

### Dependency Injection (DI)

All components are created and wired by the **DI Container**:

```python
# main.py
container = ContainerBuilder.build_container(app, loop)

application = Application(
    config_manager=container.get("config_manager"),
    device_info=container.get("device_info"),
    plugin_manager=container.get("plugin_manager"),
    server_client=container.get("server_client"),
    tray_manager=container.get("tray_manager"),
    event_bus=container.get("event_bus"),
    app=app,
    loop=loop
)
```

### EventBus Architecture

Components communicate via **EventBus** (pub/sub pattern):

```
┌─────────────┐    publish     ┌──────────────┐
│PluginManager├────────────────>│              │
└─────────────┘  PLUGIN_EVENT   │              │
                                 │              │
┌─────────────┐    publish     │   EventBus   │    subscribe    ┌─────────────┐
│ServerClient ├────────────────>│              ├─────────────────>│ Application │
└─────────────┘  SERVER_ACTION  │              │   (5 topics)    └─────────────┘
                                 │              │
┌─────────────┐    publish     │              │
│ TrayManager ├────────────────>│              │
└─────────────┘  UI_QUIT_REQ    └──────────────┘
```

**Event Topics:**
- `PLUGIN_EVENT` - Plugin trigger events → Server
- `SERVER_ACTION` - Server actions → Plugin execution
- `UI_QUIT_REQUESTED` - Quit button clicked
- `UI_SETTINGS_REQUESTED` - Settings button clicked
- `UI_SETTINGS_CHANGED` - Settings updated

### Component Interfaces

All core components implement **Protocol** interfaces for loose coupling:

```python
from core.protocols import IConfigManager, IPluginManager, IServerClient

# Components can be swapped or mocked easily
def my_function(config: IConfigManager):  # Accepts any implementation
    server_url = config.server_url
```

### Benefits

- ✅ **Decoupled** - Components don't know about each other
- ✅ **Testable** - Easy to mock dependencies (97% test coverage on core)
- ✅ **Maintainable** - Clear separation of concerns
- ✅ **Extensible** - Add new components via DI
- ✅ **Type-safe** - Protocol interfaces document contracts

## Key Conventions

### Server API

- Base URL configured in settings as `server_url`
- Auth header: `X-Device-Auth-Key` (NOT X-Api-Key)
- All payloads use **camelCase** (not snake_case):

```python
# TriggerPayload.to_dict()
{
    "id": "...",
    "type": "trigger",
    "name": "device.button.ping",
    "deviceId": "...",      # camelCase!
    "userId": "...",
    "occurredAt": "...",
    "data": {}
}
```

### Server Endpoints

- Link device: `POST /mobile-api/device/registration/link`
- Send trigger: `POST /mobile-api/device/trigger/new`
- WebSocket: Centrifugo on configured URL

### Retry Logic

HTTP and WebSocket operations use **automatic retry with exponential backoff**:

```python
from core.retry import retry_async, RetryConfig

@retry_async(RetryConfig(max_attempts=3, initial_delay=1.0))
async def my_network_call():
    # Automatically retries on transient errors (5xx, timeouts, network)
    # Fails fast on permanent errors (4xx)
    pass
```

### Centrifugo

Using `centrifuge-python` package (NOT `centrifuge`):
```
pip install centrifuge-python
```

Version 0.4.x API:
```python
from centrifuge import Client, ClientEventHandler, SubscriptionEventHandler

client = Client(ws_url, events=handler)
await client.connect()
sub = client.new_subscription(channel, events=sub_handler)
await sub.subscribe()
```

## Plugin System

See [PLUGINS.md](PLUGINS.md) for detailed plugin development guide.

### Quick Start: Trigger Plugin

```python
from core.plugin_base import TriggerPlugin

class MyTrigger(TriggerPlugin):
    @property
    def name(self) -> str:
        return "My Trigger"

    async def start(self) -> None:
        # Start monitoring
        pass

    async def stop(self) -> None:
        # Stop monitoring
        pass
```

### Quick Start: Action Plugin

```python
from core.plugin_base import ActionPlugin

class MyAction(ActionPlugin):
    @property
    def name(self) -> str:
        return "My Action"

    def get_supported_actions(self) -> list[str]:
        return ["MY_ACTION_TYPE"]

    async def execute(self, action_type: str, parameters: dict) -> bool:
        # Execute action
        return True
```

### Plugin Config Validation

Override `validate_config()` to validate plugin configuration:

```python
def validate_config(self) -> tuple[bool, str]:
    """Validate plugin configuration.

    Returns:
        (valid, error_message) tuple
    """
    value = self._config.get("my_setting")
    if not isinstance(value, int):
        return False, "my_setting must be an integer"
    if value <= 0:
        return False, "my_setting must be positive"
    return True, ""
```

If validation fails, plugin is automatically disabled.

### Emitting Events

```python
# From trigger plugin
self.emit_event("device.button.clicked", {"button_id": "123"})

# Event flows: Plugin → PluginManager → EventBus → Application → ServerClient
```

## Platform-Specific Notes

### Notifications (macOS)

`QSystemTrayIcon.showMessage()` doesn't work for unbundled Python apps on macOS.

Solution in `ui/tray.py`:
1. **terminal-notifier** (preferred) — `brew install terminal-notifier`
2. **osascript** fallback

### TTS

Uses system tools (no pyttsx3 dependency):
- **macOS**: `say` command (built-in)
- **Linux**: `espeak` or `spd-say`
- **Windows**: PowerShell + SAPI (built-in)

Plugin shows status if tool not found: `TTS: No TTS tool found`

### Qt Lambda Callbacks

When using lambdas for Qt menu callbacks, always handle the `checked` argument:

```python
# WRONG - Qt passes checked as first arg, overrides captured value
callback = lambda item=item: on_click(item)

# CORRECT
callback = lambda checked=False, item=item: on_click(item)
```

## Testing

Comprehensive test suite with **313 tests** and **high coverage**:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=core --cov=ui --cov=plugins

# Run specific test file
pytest tests/test_application.py -v
```

**Key Coverage:**
- Application: 97%
- DI Container: 88%
- EventBus: 92%
- Protocols: 100%
- Plugin Manager: 82%
- Server Client: 80%

## Build

### Development

```bash
pip install -r requirements.txt
python main.py
```

### Production Build

```bash
pip install pyinstaller
python build.py all
```

Output:
- **macOS**: `dist/AgimateDesktop.app` (hidden from Dock, menu bar only)
- **Windows/Linux**: `dist/AgimateDesktop` executable

### Linux AppImage

Uses `python-appimage` for building.

```bash
# On Linux (native)
./build_appimage.sh

# On macOS/Windows (via Docker)
./build_appimage.sh  # automatically uses --docker flag
```

Output: `dist/AgimateDesktop-x86_64.AppImage`

Requirements:
- `pip install python-appimage`
- Docker (for non-Linux builds)

### Bundled App Paths

When running as bundled app, configs are stored in user data directory:
- **macOS**: `~/Library/Application Support/AgimateDesktop/`
- **Windows**: `%LOCALAPPDATA%/AgimateDesktop/`
- **Linux**: `~/.config/agimatedesktop/`

Use `core/paths.py` utilities:
```python
from core.paths import get_app_dir, get_data_dir, get_plugins_dir, is_bundled
```

## Error Handling

### Retry Strategy

Network operations automatically retry with exponential backoff:
- HTTP requests: 3 attempts, 1s initial delay
- WebSocket reconnect: 10 attempts max, exponential backoff
- Transient errors (5xx, timeouts) → retry
- Permanent errors (4xx) → fail fast

### Validation

Settings and plugin configs are validated before use:
- Server URL must be valid HTTP/HTTPS
- API key must be ≥10 characters (if not empty)
- Plugin configs validated via `validate_config()`
- Invalid configs → plugin disabled with error message

### Graceful Degradation

- Plugin manager failure → continue without plugins
- Individual plugin failure → marked as failed, others continue
- Server connection failure → retry with backoff
- Non-critical errors logged, don't crash app

## Visual Buttons Plugin

Config format (`plugins/triggers/visual_buttons/config.json`):

```json
{
  "enabled": true,
  "grid_columns": 3,
  "buttons": [
    {
      "button_name": "Quick Note",
      "trigger_name": "device.button.quick_note",
      "type": "dialog",
      "params": {},
      "dialog_params": {
        "input_label": "Note",
        "input_type": "textarea"
      }
    },
    {
      "button_name": "Ping",
      "trigger_name": "device.button.ping",
      "type": "direct",
      "params": {}
    }
  ]
}
```

Button types:
- `direct` — sends trigger immediately
- `dialog` — shows input dialog first, adds `user_input` to trigger data
