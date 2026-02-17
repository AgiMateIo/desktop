# Agimate Desktop

Cross-platform system tray agent with plugin architecture for triggers and actions.

## Features

- 🔌 **Plugin Architecture** — Extensible trigger and action system
- 🏗️ **Clean Architecture** — Dependency Injection and EventBus for decoupled design
- 🖥️ **Cross-Platform** — Works on macOS, Windows, and Linux
- 🌐 **Server Integration** — HTTP triggers and WebSocket actions via Centrifugo
- 🎯 **System Tray** — Background agent with tray icon
- 🔄 **Robust Error Handling** — Automatic retry with exponential backoff
- ✅ **Well Tested** — 313 tests with 97% coverage on core components
- 📦 **Bundled Apps** — Single executable with PyInstaller

## Architecture

Agimate Desktop uses modern software architecture patterns:

- **Dependency Injection** - Components receive dependencies via constructor
- **EventBus** - Pub/sub pattern for decoupled communication
- **Protocol Interfaces** - Type-safe contracts between components
- **Async-First** - Non-blocking I/O throughout the application

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd agimate-desktop

# Install dependencies
pip install -e ".[server]"
```

### Running

```bash
# Run the agent
python main.py
```

The application will:
1. Build the DI container
2. Initialize all components
3. Load and start plugins
4. Connect to the server (if configured)
5. Show system tray icon

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[test,server]"
```

### Running Tests

The project uses pytest with comprehensive test coverage (313 tests).

#### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage report
pytest --cov=core --cov=ui --cov=plugins --cov-report=term-missing
```

#### Run Specific Tests

```bash
# Run tests for a specific module
pytest tests/test_application.py

# Run tests for multiple modules
pytest tests/test_application.py tests/test_event_bus.py

# Run a specific test class
pytest tests/test_application.py::TestApplicationInit

# Run a specific test function
pytest tests/test_application.py::TestApplicationInit::test_init
```

#### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=core --cov=ui --cov=plugins --cov-report=html

# Open HTML report (macOS)
open htmlcov/index.html

# Open HTML report (Linux)
xdg-open htmlcov/index.html

# Open HTML report (Windows)
start htmlcov/index.html
```

#### Test Options

```bash
# Run tests with different verbosity levels
pytest -v          # Verbose
pytest -vv         # More verbose
pytest -q          # Quiet

# Stop on first failure
pytest -x

# Show local variables in tracebacks
pytest -l

# Run only tests that failed last time
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

### Code Coverage

Current coverage for core components:

- **Application**: 97% ⭐
- **DI Container**: 88% ⭐
- **EventBus**: 92% ⭐
- **Protocols**: 100% ⭐
- **Plugin Manager**: 82% ✅
- **Server Client**: 80% ✅
- **Config Manager**: 100% ⭐

Project aims for **80%+ coverage** on all core modules.

## Project Structure

```
agimate-desktop/
├── main.py                 # Entry point with DI architecture
├── core/                   # Core system modules
│   ├── application.py      # Application coordinator
│   ├── di_container.py     # Dependency injection container
│   ├── event_bus.py        # EventBus for pub/sub communication
│   ├── protocols.py        # Protocol interfaces for DI
│   ├── config_manager.py   # Configuration management
│   ├── device_info.py      # Device identification
│   ├── plugin_manager.py   # Plugin lifecycle
│   ├── server_client.py    # HTTP + WebSocket client
│   ├── retry.py            # Retry logic with exponential backoff
│   ├── models.py           # Data models
│   └── paths.py            # Path utilities
├── ui/                     # User interface
│   ├── tray.py             # System tray manager
│   └── settings.py         # Settings window
├── plugins/                # Plugin implementations
│   ├── triggers/           # Trigger plugins
│   │   ├── file_watcher/   # File system monitoring
│   │   └── visual_buttons/ # Manual trigger buttons
│   └── actions/            # Action plugins
│       ├── show_notification/  # Notifications
│       └── tts/            # Text-to-speech
└── tests/                  # Comprehensive test suite (313 tests)
    ├── conftest.py         # Shared fixtures
    ├── test_application.py # Application tests
    ├── test_di_container.py # DI container tests
    ├── test_event_bus.py   # EventBus tests
    └── ...                 # More tests
```

## Building

### Build for Current Platform

```bash
# Build with PyInstaller
python build.py all
```

### Build Linux AppImage

```bash
# On Linux (native)
./build_appimage.sh

# On macOS/Windows (via Docker)
./build_appimage.sh
```

Output:
- **macOS**: `dist/AgimateDesktop.app`
- **Windows/Linux**: `dist/AgimateDesktop`
- **Linux AppImage**: `dist/AgimateDesktop-x86_64.AppImage`

## Configuration

Configuration is stored in platform-specific locations:

- **macOS**: `~/Library/Application Support/AgimateDesktop/config.json`
- **Windows**: `%LOCALAPPDATA%/AgimateDesktop/config.json`
- **Linux**: `~/.config/agimatedesktop/config.json`

Example configuration:

```json
{
  "server_url": "http://localhost:8080",
  "api_key": "your-api-key",
  "auto_connect": true,
  "reconnect_interval": 5000,
  "log_level": "INFO"
}
```

## Plugin Development

See [PLUGINS.md](PLUGINS.md) for comprehensive plugin development guide.

### Quick Example: Create a Trigger Plugin

```python
from core.plugin_base import TriggerPlugin

class MyTrigger(TriggerPlugin):
    @property
    def name(self) -> str:
        return "My Trigger"

    async def initialize(self) -> None:
        # Initialize plugin
        self.interval = self.get_config("interval", 60)

    async def start(self) -> None:
        # Start monitoring
        self._running = True
        while self._running:
            # Detect event
            if self._check_condition():
                self.emit_event("desktop.trigger.my_plugin.detected", {"data": "value"})
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        # Stop monitoring
        self._running = False

    async def shutdown(self) -> None:
        # Cleanup
        await self.stop()
```

### Quick Example: Create an Action Plugin

```python
from core.plugin_base import ActionPlugin

class MyAction(ActionPlugin):
    @property
    def name(self) -> str:
        return "My Action"

    def get_supported_actions(self) -> list[str]:
        return ["MY_CUSTOM_ACTION"]

    async def execute(self, action_type: str, parameters: dict) -> bool:
        if action_type == "MY_CUSTOM_ACTION":
            message = parameters.get("message")
            # Perform action
            print(f"Executing: {message}")
            return True
        return False
```

## Naming Convention

Trigger and action names follow a unified naming scheme across all Agimate platforms:

```
{platform}.trigger.{plugin}.{event}
{platform}.action.{plugin}.{verb}
```

- **platform** — `desktop`, `android`, `ios`, etc.
- **trigger/action** — fixed literal
- **plugin** — plugin or module name (e.g. `filewatcher`, `tts`, `notification`)
- **event/verb** — specific event or action (e.g. `created`, `speak`, `show`)

### Desktop Triggers

| Name | Params |
|------|--------|
| `desktop.trigger.filewatcher.created` | path, filename |
| `desktop.trigger.filewatcher.modified` | path, filename |
| `desktop.trigger.filewatcher.deleted` | path, filename |
| `desktop.trigger.filewatcher.moved` | path, filename, src_path |
| `desktop.trigger.visualbuttons.*` | (configurable) |

### Desktop Actions

| Name | Params |
|------|--------|
| `desktop.action.notification.show` | title, message, duration, modal |
| `desktop.action.notification.show_modal` | title, message, duration, modal |
| `desktop.action.tts.speak` | text, voice, rate |
| `desktop.action.tts.stop` | — |

## Key Features

### Dependency Injection

Components are created and wired by the DI Container:

```python
# main.py
container = ContainerBuilder.build_container(app, loop)
application = Application(
    config_manager=container.get("config_manager"),
    plugin_manager=container.get("plugin_manager"),
    server_client=container.get("server_client"),
    event_bus=container.get("event_bus"),
    # ... other components
)
```

### EventBus Architecture

Components communicate via EventBus (pub/sub pattern):

- Plugin events → EventBus → Application → Server
- Server actions → EventBus → Application → Plugins
- UI events → EventBus → Application

### Automatic Retry

Network operations automatically retry with exponential backoff:

- HTTP requests: 3 attempts, exponential delay
- WebSocket reconnect: 10 attempts max
- Transient errors (5xx, timeouts) → retry
- Permanent errors (4xx) → fail fast

### Config Validation

Settings and plugin configs are validated before use:

- Invalid configs → plugin disabled with error message
- Clear validation errors in logs
- Graceful degradation on failures

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Architecture, conventions, and technical details
- **[PLUGINS.md](PLUGINS.md)** - Complete plugin development guide
- **[tests/](tests/)** - Examples of testing patterns

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure tests pass: `pytest`
5. Ensure coverage: `pytest --cov=core --cov=ui`
6. Submit a pull request

### Development Workflow

```bash
# Run tests during development
pytest -v

# Run tests with coverage
pytest --cov=core --cov=ui --cov-report=term-missing

# Run tests in watch mode (requires pytest-watch)
ptw

# Check specific module
pytest tests/test_application.py -v
```

## License

MIT License

## Support

For issues and questions, please use the GitHub issue tracker.

## Changelog

### v0.2.0 - Architecture Refactoring

- ✨ Implemented Dependency Injection architecture
- ✨ Added EventBus for pub/sub communication
- ✨ Protocol interfaces for type-safe contracts
- ✨ Automatic retry with exponential backoff
- ✨ Comprehensive config validation
- ✨ 313 tests with 97% coverage on core
- 📚 Complete documentation (CLAUDE.md, PLUGINS.md)
- 🔧 Improved error handling and logging
