# System Agent

Cross-platform system tray agent with plugin architecture for triggers and actions.

## Features

- 🔌 **Plugin Architecture** — Extensible trigger and action system
- 🖥️ **Cross-Platform** — Works on macOS, Windows, and Linux
- 🌐 **Server Integration** — HTTP triggers and WebSocket actions via Centrifugo
- 🎯 **System Tray** — Background agent with tray icon
- 📦 **Bundled Apps** — Single executable with PyInstaller

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd system-agent

# Install dependencies
pip install -e ".[server]"
```

### Running

```bash
# Run the agent
python main.py
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[test,server]"
```

### Running Tests

The project uses pytest for testing with coverage reporting.

#### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage report
pytest --cov=core --cov=plugins --cov-report=term-missing
```

#### Run Specific Tests

```bash
# Run tests for a specific module
pytest tests/test_models.py

# Run tests for multiple modules
pytest tests/test_models.py tests/test_paths.py

# Run a specific test class
pytest tests/test_models.py::TestTriggerPayload

# Run a specific test function
pytest tests/test_models.py::TestTriggerPayload::test_to_dict_camel_case
```

#### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=core --cov=plugins --cov-report=html

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

#### Continuous Testing

```bash
# Watch for file changes and re-run tests (requires pytest-watch)
ptw
```

### Code Coverage Goals

The project aims for **80%+ code coverage** for core modules and plugins.

Current coverage can be viewed by running:
```bash
pytest --cov=core --cov=plugins --cov-report=term-missing
```

## Project Structure

```
system-agent/
├── main.py                 # Entry point
├── core/                   # Core system modules
│   ├── config_manager.py   # Configuration management
│   ├── device_info.py      # Device identification
│   ├── models.py           # Data models
│   ├── paths.py            # Path utilities
│   ├── plugin_base.py      # Plugin base classes
│   ├── plugin_manager.py   # Plugin lifecycle
│   └── server_client.py    # HTTP + WebSocket client
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
└── tests/                  # Test suite
    ├── conftest.py         # Shared fixtures
    ├── test_models.py      # Model tests
    ├── test_paths.py       # Path utility tests
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
- **macOS**: `dist/SystemAgent.app`
- **Windows/Linux**: `dist/SystemAgent`
- **Linux AppImage**: `dist/SystemAgent-x86_64.AppImage`

## Configuration

Configuration is stored in platform-specific locations:

- **macOS**: `~/Library/Application Support/SystemAgent/config.json`
- **Windows**: `%LOCALAPPDATA%/SystemAgent/config.json`
- **Linux**: `~/.config/systemagent/config.json`

## Plugin Development

See [CLAUDE.md](CLAUDE.md) for detailed plugin development guide.

### Quick Example: Create a Trigger Plugin

```python
from core.plugin_base import TriggerPlugin

class MyTrigger(TriggerPlugin):
    @property
    def name(self) -> str:
        return "My Trigger"

    async def initialize(self) -> None:
        # Initialize plugin
        pass

    async def shutdown(self) -> None:
        # Cleanup
        pass

    async def start(self) -> None:
        # Start monitoring
        self.emit_event("device.my.event", {"data": "value"})

    async def stop(self) -> None:
        # Stop monitoring
        pass
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure tests pass: `pytest`
5. Ensure coverage: `pytest --cov=core --cov=plugins`
6. Submit a pull request

## License

MIT License

## Support

For issues and questions, please use the GitHub issue tracker.
