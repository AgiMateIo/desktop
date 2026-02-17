"""Tests for core.models module."""

import pytest
from datetime import datetime
from core.models import TriggerPayload, ToolTask


class TestTriggerPayload:
    """Test cases for TriggerPayload dataclass."""

    def test_init_with_required_fields(self):
        """Test TriggerPayload initialization with required fields."""
        payload = TriggerPayload(
            name="device.test.event",
            data={"key": "value"},
            device_id="test-device-123"
        )

        assert payload.name == "device.test.event"
        assert payload.data == {"key": "value"}
        assert payload.device_id == "test-device-123"
        assert payload.type == "DEVICE_EVENT"
        assert payload.source == "desktop-agent"
        assert payload.user_id is None

    def test_default_values(self):
        """Test default values are generated correctly."""
        payload = TriggerPayload(
            name="device.test",
            data={},
            device_id="test-123"
        )

        # ID should be a UUID
        assert len(payload.id) == 36
        assert payload.id.count("-") == 4

        # Type should have default
        assert payload.type == "DEVICE_EVENT"

        # Source should have default
        assert payload.source == "desktop-agent"

        # occurred_at should be ISO format with Z suffix
        assert payload.occurred_at.endswith("Z")
        assert "T" in payload.occurred_at

    def test_to_dict_camel_case(self, sample_trigger_payload):
        """Test to_dict() converts to camelCase for server."""
        result = sample_trigger_payload.to_dict()

        # Check camelCase conversion
        assert "deviceId" in result
        assert "userId" in result
        assert "occurredAt" in result

        # Check snake_case is NOT present
        assert "device_id" not in result
        assert "user_id" not in result
        assert "occurred_at" not in result

    def test_to_dict_values(self, sample_trigger_payload):
        """Test to_dict() preserves all values correctly."""
        result = sample_trigger_payload.to_dict()

        assert result["name"] == "device.test.event"
        assert result["data"] == {"key": "value"}
        assert result["deviceId"] == "test-device-123"
        assert result["type"] == "DEVICE_EVENT"
        assert result["source"] == "desktop-agent"
        assert result["userId"] is None
        assert "id" in result
        assert "occurredAt" in result

    def test_to_dict_with_user_id(self):
        """Test to_dict() with user_id set."""
        payload = TriggerPayload(
            name="device.test",
            data={},
            device_id="test-123",
            user_id="user-456"
        )

        result = payload.to_dict()
        assert result["userId"] == "user-456"

    def test_empty_data(self):
        """Test TriggerPayload with empty data dict."""
        payload = TriggerPayload(
            name="device.empty",
            data={},
            device_id="test-123"
        )

        result = payload.to_dict()
        assert result["data"] == {}

    def test_complex_data(self):
        """Test TriggerPayload with complex nested data."""
        complex_data = {
            "level1": {
                "level2": {
                    "value": 123
                },
                "list": [1, 2, 3]
            },
            "string": "test",
            "number": 42
        }

        payload = TriggerPayload(
            name="device.complex",
            data=complex_data,
            device_id="test-123"
        )

        result = payload.to_dict()
        assert result["data"] == complex_data


class TestToolTask:
    """Test cases for ToolTask dataclass."""

    def test_init(self):
        """Test ToolTask initialization."""
        task = ToolTask(
            type="desktop.tool.notification.show",
            parameters={"title": "Test", "message": "Message"}
        )

        assert task.type == "desktop.tool.notification.show"
        assert task.parameters == {"title": "Test", "message": "Message"}

    def test_from_dict_basic(self):
        """Test from_dict() with basic data."""
        data = {
            "type": "desktop.tool.notification.show",
            "parameters": {
                "title": "Test",
                "message": "Test message"
            }
        }

        task = ToolTask.from_dict(data)

        assert task.type == "desktop.tool.notification.show"
        assert task.parameters["title"] == "Test"
        assert task.parameters["message"] == "Test message"

    def test_from_dict_missing_type(self):
        """Test from_dict() with missing type defaults to empty string."""
        data = {
            "parameters": {"key": "value"}
        }

        task = ToolTask.from_dict(data)

        assert task.type == ""
        assert task.parameters == {"key": "value"}

    def test_from_dict_missing_parameters(self):
        """Test from_dict() with missing parameters defaults to empty dict."""
        data = {
            "type": "desktop.tool.tts.speak"
        }

        task = ToolTask.from_dict(data)

        assert task.type == "desktop.tool.tts.speak"
        assert task.parameters == {}

    def test_from_dict_empty(self):
        """Test from_dict() with empty dict."""
        data = {}

        task = ToolTask.from_dict(data)

        assert task.type == ""
        assert task.parameters == {}

    def test_different_tool_types(self):
        """Test ToolTask with different tool types."""
        types = [
            "desktop.tool.notification.show",
            "desktop.tool.notification.show_modal",
            "desktop.tool.tts.speak",
            "desktop.tool.tts.stop",
        ]

        for tool_type in types:
            task = ToolTask(type=tool_type, parameters={})
            assert task.type == tool_type

    def test_sample_fixture(self, sample_tool_task):
        """Test using the sample_tool_task fixture."""
        assert sample_tool_task.type == "desktop.tool.notification.show"
        assert sample_tool_task.parameters["title"] == "Test"
        assert sample_tool_task.parameters["message"] == "Test message"
