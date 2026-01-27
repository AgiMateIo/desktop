# System Agent

Cross-platform system tray agent with plugin architecture for triggers and actions.

## Project Structure

```
system-agent/
├── main.py                 # Entry point, SystemAgent class
├── build.py                # Build script for PyInstaller
├── system_agent.spec       # PyInstaller configuration
├── requirements.txt        # Dependencies
├── core/
│   ├── plugin_base.py      # Base classes: TriggerPlugin, ActionPlugin
│   ├── plugin_manager.py   # Plugin discovery and lifecycle
│   ├── config_manager.py   # App configuration
│   ├── device_info.py      # Device ID and platform info
│   ├── server_client.py    # HTTP + WebSocket/Centrifugo client
│   ├── models.py           # TriggerPayload, ActionTask
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

### Creating a Trigger Plugin

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

    # Optional: plugin window
    def has_window(self) -> bool:
        return True

    def create_window(self, parent=None):
        return MyPluginWindow(self, parent)
```

### Creating an Action Plugin

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

### Plugin Config

Each plugin has `config.json` in its directory:
```json
{
  "enabled": true,
  // plugin-specific settings
}
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
- **macOS**: `dist/SystemAgent.app` (hidden from Dock, menu bar only)
- **Windows/Linux**: `dist/SystemAgent` executable

### Linux AppImage

Uses `python-appimage` for building.

```bash
# On Linux (native)
./build_appimage.sh

# On macOS/Windows (via Docker)
./build_appimage.sh  # automatically uses --docker flag
```

Output: `dist/SystemAgent-x86_64.AppImage`

Requirements:
- `pip install python-appimage`
- Docker (for non-Linux builds)

### Bundled App Paths

When running as bundled app, configs are stored in user data directory:
- **macOS**: `~/Library/Application Support/SystemAgent/`
- **Windows**: `%LOCALAPPDATA%/SystemAgent/`
- **Linux**: `~/.config/systemagent/`

Use `core/paths.py` utilities:
```python
from core.paths import get_app_dir, get_data_dir, get_plugins_dir, is_bundled
```

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
