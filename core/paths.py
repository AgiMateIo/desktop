"""Path utilities for bundled application support."""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Get the application directory.

    Returns the directory containing the application files.
    - For bundled app: the temp directory where files are extracted
    - For script: the directory containing main.py
    """
    if getattr(sys, 'frozen', False):
        # Running as bundled app (PyInstaller)
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get the user data directory for config and runtime data.

    Returns a writable directory for storing user configuration.
    This is separate from app_dir because bundled apps extract to
    a read-only temp directory.
    """
    if getattr(sys, 'frozen', False):
        # Bundled: use user's app data directory
        if sys.platform == 'darwin':
            data_dir = Path.home() / 'Library' / 'Application Support' / 'SystemAgent'
        elif sys.platform == 'win32':
            data_dir = Path.home() / 'AppData' / 'Local' / 'SystemAgent'
        else:
            data_dir = Path.home() / '.config' / 'systemagent'
    else:
        # Script: use script directory
        data_dir = Path(__file__).parent.parent

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_plugins_dir() -> Path:
    """Get the plugins directory."""
    return get_app_dir() / 'plugins'


def get_config_path() -> Path:
    """Get the main config file path."""
    return get_data_dir() / 'config.json'


def is_bundled() -> bool:
    """Check if running as bundled application."""
    return getattr(sys, 'frozen', False)
