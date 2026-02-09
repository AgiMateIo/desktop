"""Mock action plugin for testing."""

from core.plugin_base import ActionPlugin


class MockAction(ActionPlugin):
    """Mock action plugin for testing."""

    def __init__(self, plugin_dir):
        super().__init__(plugin_dir)
        self.initialized = False
        self.executed_actions = []

    @property
    def name(self) -> str:
        return "Mock Action"

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.initialized = False

    def get_supported_actions(self) -> list[str]:
        """Get list of supported action types."""
        return ["MOCK_ACTION", "MOCK_ACTION_2"]

    def get_capabilities(self) -> dict[str, list[str]]:
        """Return mock action capabilities."""
        return {
            "MOCK_ACTION": ["param1", "param2"],
            "MOCK_ACTION_2": ["param3"],
        }

    async def execute(self, action_type: str, parameters: dict) -> bool:
        """Execute an action."""
        self.executed_actions.append((action_type, parameters))

        # Simulate success/failure based on parameters
        if parameters.get("should_fail"):
            return False

        return True
