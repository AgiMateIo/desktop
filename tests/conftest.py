"""Shared pytest fixtures for Agimate Desktop tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_device_id():
    """Provide a consistent mock device ID."""
    return "test-device-12345"


@pytest.fixture
def mock_platform(monkeypatch):
    """Mock platform.system() for consistent testing."""
    def _mock_platform(system_name="Linux"):
        monkeypatch.setattr("platform.system", lambda: system_name)
    return _mock_platform


@pytest.fixture
def mock_frozen(monkeypatch):
    """Mock sys.frozen for bundled app testing."""
    def _mock_frozen(frozen=False, meipass="/tmp/meipass"):
        if frozen:
            import sys
            monkeypatch.setattr(sys, "frozen", True, raising=False)
            monkeypatch.setattr(sys, "_MEIPASS", meipass)
        else:
            monkeypatch.delattr("sys.frozen", raising=False)
    return _mock_frozen


@pytest.fixture
def sample_trigger_payload():
    """Provide a sample TriggerPayload for testing."""
    from core.models import TriggerPayload
    return TriggerPayload(
        name="device.test.event",
        data={"key": "value"},
        device_id="test-device-123"
    )


@pytest.fixture
def sample_tool_task():
    """Provide a sample ToolTask for testing."""
    from core.models import ToolTask
    return ToolTask(
        type="desktop.tool.notification.show",
        parameters={"title": "Test", "message": "Test message"}
    )
