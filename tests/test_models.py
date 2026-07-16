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
        assert "occurredAt" in result

        # Check snake_case is NOT present
        assert "device_id" not in result
        assert "occurred_at" not in result

        # userId should not be in payload
        assert "userId" not in result

    def test_to_dict_values(self, sample_trigger_payload):
        """Test to_dict() preserves all values correctly."""
        result = sample_trigger_payload.to_dict()

        assert result["name"] == "device.test.event"
        assert result["data"] == {"key": "value"}
        assert result["deviceId"] == "test-device-123"
        assert result["type"] == "DEVICE_EVENT"
        assert result["source"] == "desktop-agent"
        assert "id" in result
        assert "occurredAt" in result

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
            id="tool-123",
            name="notification_show",
            params={"title": "Test", "message": "Message"}
        )

        assert task.id == "tool-123"
        assert task.name == "notification_show"
        assert task.params == {"title": "Test", "message": "Message"}

    def test_from_dict_basic(self):
        """Test from_dict() with basic data."""
        data = {
            "id": "tool-123",
            "name": "notification_show",
            "params": {
                "title": "Test",
                "message": "Test message"
            }
        }

        task = ToolTask.from_dict(data)

        assert task.id == "tool-123"
        assert task.name == "notification_show"
        assert task.params["title"] == "Test"
        assert task.params["message"] == "Test message"

    def test_from_dict_missing_name(self):
        """Test from_dict() with missing name defaults to empty string."""
        data = {
            "params": {"key": "value"}
        }

        task = ToolTask.from_dict(data)

        assert task.id == ""
        assert task.name == ""
        assert task.params == {"key": "value"}

    def test_from_dict_missing_params(self):
        """Test from_dict() with missing params defaults to empty dict."""
        data = {
            "id": "tool-456",
            "name": "tts_speak"
        }

        task = ToolTask.from_dict(data)

        assert task.name == "tts_speak"
        assert task.params == {}

    def test_from_dict_empty(self):
        """Test from_dict() with empty dict."""
        data = {}

        task = ToolTask.from_dict(data)

        assert task.id == ""
        assert task.name == ""
        assert task.params == {}

    def test_from_dict_input_field(self):
        """Test from_dict() reads params from 'input' (current contract)."""
        data = {
            "id": "01951234-abcd-ef01-2345-6789abcdef77",
            "connectorCode": "smarthome",
            "connectionId": "01951234-abcd-ef01-2345-6789abcdef02",
            "name": "tool.device.tts.speak",
            "input": {"text": "Привет"},
            "agentSessionId": "session-1",
        }

        task = ToolTask.from_dict(data)

        assert task.id == "01951234-abcd-ef01-2345-6789abcdef77"
        assert task.name == "tool.device.tts.speak"
        assert task.params == {"text": "Привет"}
        assert task.connector_code == "smarthome"

    def test_from_dict_input_takes_precedence_over_params(self):
        """Test from_dict() prefers 'input' over legacy 'params'."""
        data = {
            "id": "tool-1",
            "name": "tool.x",
            "input": {"a": 1},
            "params": {"b": 2},
        }

        task = ToolTask.from_dict(data)

        assert task.params == {"a": 1}

    def test_from_dict_enveloped_payload(self):
        """Test from_dict() unwraps {"type": "toolCall", "payload": {...}}."""
        data = {
            "type": "toolCall",
            "payload": {
                "id": "server-id-1",
                "name": "tool.device.notification.show",
                "input": {"title": "Hi"},
            },
        }

        task = ToolTask.from_dict(data)

        assert task.id == "server-id-1"
        assert task.name == "tool.device.notification.show"
        assert task.params == {"title": "Hi"}

    def test_different_tool_types(self):
        """Test ToolTask with different tool types."""
        types = [
            "notification_show",
            "notification_show_modal",
            "tts_speak",
            "tts_stop",
        ]

        for tool_type in types:
            task = ToolTask(id="test", name=tool_type, params={})
            assert task.name == tool_type

    def test_sample_fixture(self, sample_tool_task):
        """Test using the sample_tool_task fixture."""
        assert sample_tool_task.name == "notification_show"
        assert sample_tool_task.params["title"] == "Test"
        assert sample_tool_task.params["message"] == "Test message"
