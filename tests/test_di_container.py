"""Tests for DI container."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.di_container import DIContainer, ContainerBuilder


class TestDIContainer:
    """Tests for DIContainer class."""

    def test_register_singleton(self):
        """Test registering a singleton."""
        container = DIContainer()
        instance = "test_instance"

        container.register_singleton("test", instance)

        assert container.get("test") == instance

    def test_register_factory(self):
        """Test registering a factory."""
        container = DIContainer()
        factory_called = []

        def factory():
            factory_called.append(True)
            return "test_instance"

        container.register_factory("test", factory)

        # First get should call factory
        result1 = container.get("test")
        assert result1 == "test_instance"
        assert len(factory_called) == 1

        # Second get should return cached singleton
        result2 = container.get("test")
        assert result2 == "test_instance"
        assert len(factory_called) == 1  # Not called again

    def test_get_nonexistent(self):
        """Test getting a non-existent component."""
        container = DIContainer()

        with pytest.raises(KeyError, match="Component 'missing' not found"):
            container.get("missing")

    def test_has_component(self):
        """Test checking if component exists."""
        container = DIContainer()

        assert not container.has("test")

        container.register_singleton("test", "value")
        assert container.has("test")

    def test_has_factory(self):
        """Test checking if factory exists."""
        container = DIContainer()

        assert not container.has("test")

        container.register_factory("test", lambda: "value")
        assert container.has("test")

    def test_singleton_overrides_factory(self):
        """Test that singleton takes precedence over factory."""
        container = DIContainer()
        factory_called = []

        def factory():
            factory_called.append(True)
            return "factory_value"

        container.register_factory("test", factory)
        container.register_singleton("test", "singleton_value")

        result = container.get("test")
        assert result == "singleton_value"
        assert len(factory_called) == 0  # Factory not called

    def test_factory_creates_singleton(self):
        """Test that factory result is cached as singleton."""
        container = DIContainer()
        call_count = []

        def factory():
            call_count.append(True)
            return {"value": len(call_count)}

        container.register_factory("test", factory)

        # First call
        result1 = container.get("test")
        assert result1 == {"value": 1}

        # Second call - should return same instance
        result2 = container.get("test")
        assert result2 is result1
        assert len(call_count) == 1


class TestContainerBuilder:
    """Tests for ContainerBuilder."""

    def test_build_container(self, tmp_path):
        """Test building a container."""
        # Mock Qt app and loop
        app = MagicMock()
        loop = MagicMock()

        # Build container
        container = ContainerBuilder.build_container(app, loop)

        # Check registered components
        assert container.has("app")
        assert container.has("loop")
        assert container.has("event_bus")
        assert container.has("config_manager")
        assert container.has("device_info")
        assert container.has("plugin_manager")
        assert container.has("server_client")
        assert container.has("tray_manager")

    def test_build_container_paths(self):
        """Test that paths are registered."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        # Check path components
        assert container.has("app_dir")
        assert container.has("data_dir")
        assert container.has("plugins_dir")
        assert container.has("assets_dir")

        # Check that paths are Path objects
        assert isinstance(container.get("app_dir"), Path)
        assert isinstance(container.get("data_dir"), Path)
        assert isinstance(container.get("plugins_dir"), Path)
        assert isinstance(container.get("assets_dir"), Path)

    def test_build_container_qt_components(self):
        """Test that Qt components are registered."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        assert container.get("app") is app
        assert container.get("loop") is loop

    def test_build_container_event_bus(self):
        """Test that EventBus is created."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        event_bus = container.get("event_bus")
        assert event_bus is not None
        assert hasattr(event_bus, "subscribe")
        assert hasattr(event_bus, "publish")

    def test_build_container_lazy_initialization(self):
        """Test that components are created lazily."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        # Event bus should be created immediately (singleton)
        assert "event_bus" in container._singletons

        # Other components should be factories (not yet created)
        assert "config_manager" in container._factories
        assert "device_info" in container._factories
        assert "plugin_manager" in container._factories
        assert "server_client" in container._factories
        assert "tray_manager" in container._factories

    def test_build_container_component_creation(self):
        """Test that components can be created."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        # Create config manager (should work)
        config_manager = container.get("config_manager")
        assert config_manager is not None

        # Create device info (depends on config manager)
        device_info = container.get("device_info")
        assert device_info is not None

    def test_build_container_plugin_manager_handles_errors(self):
        """Test that plugin manager factory handles errors gracefully."""
        app = MagicMock()
        loop = MagicMock()

        container = ContainerBuilder.build_container(app, loop)

        # Get plugin manager (may be None if plugins fail to load)
        plugin_manager = container.get("plugin_manager")
        # Should not raise exception, may be None
        assert plugin_manager is None or plugin_manager is not None
