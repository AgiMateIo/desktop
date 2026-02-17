"""Mock trigger plugin for testing."""

from core.plugin_base import TriggerPlugin


class MockTrigger(TriggerPlugin):
    """Mock trigger plugin for testing."""

    def __init__(self, plugin_dir):
        super().__init__(plugin_dir)
        self.initialized = False
        self.started = False

    @property
    def name(self) -> str:
        return "Mock Trigger"

    @property
    def description(self) -> str:
        return "Mock trigger for testing"

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.initialized = False

    async def start(self) -> None:
        """Start the trigger."""
        self.started = True
        self._running = True
        # Emit a test event
        self.emit_event("desktop.trigger.mock.triggered", {"test": "data"})

    def get_capabilities(self) -> dict[str, dict]:
        """Return mock trigger capabilities."""
        return {
            "desktop.trigger.mock.triggered": {
                "params": ["test"],
                "description": "Mock trigger event",
            },
        }

    async def stop(self) -> None:
        """Stop the trigger."""
        self.started = False
        self._running = False
