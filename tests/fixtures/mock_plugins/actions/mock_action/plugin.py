"""Mock action plugin for testing."""

from core.plugin_base import ActionPlugin
from core.models import ActionResult


class MockAction(ActionPlugin):
    """Mock action plugin for testing."""

    def __init__(self, plugin_dir):
        super().__init__(plugin_dir)
        self.initialized = False
        self.executed_actions = []

    @property
    def name(self) -> str:
        return "Mock Action"

    @property
    def description(self) -> str:
        return "Mock action for testing"

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.initialized = False

    def get_supported_actions(self) -> list[str]:
        """Get list of supported action types."""
        return ["MOCK_ACTION", "MOCK_ACTION_2"]

    def get_capabilities(self) -> dict[str, dict]:
        """Return mock action capabilities."""
        return {
            "MOCK_ACTION": {"params": ["param1", "param2"], "description": "Mock action 1"},
            "MOCK_ACTION_2": {"params": ["param3"], "description": "Mock action 2"},
        }

    async def execute(self, action_type: str, parameters: dict) -> ActionResult:
        """Execute an action."""
        self.executed_actions.append((action_type, parameters))

        # Simulate success/failure based on parameters
        if parameters.get("should_fail"):
            return ActionResult(success=False, error="Simulated failure")

        return ActionResult(success=True)
