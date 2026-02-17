"""Mock tool plugin for testing."""

from core.plugin_base import ToolPlugin
from core.models import ToolResult


class MockTool(ToolPlugin):
    """Mock tool plugin for testing."""

    def __init__(self, plugin_dir):
        super().__init__(plugin_dir)
        self.initialized = False
        self.executed_tools = []

    @property
    def name(self) -> str:
        return "Mock Tool"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.initialized = True

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.initialized = False

    def get_supported_tools(self) -> list[str]:
        """Get list of supported tool types."""
        return ["MOCK_TOOL", "MOCK_TOOL_2"]

    def get_capabilities(self) -> dict[str, dict]:
        """Return mock tool capabilities."""
        return {
            "MOCK_TOOL": {"params": ["param1", "param2"], "description": "Mock tool 1"},
            "MOCK_TOOL_2": {"params": ["param3"], "description": "Mock tool 2"},
        }

    async def execute(self, tool_type: str, parameters: dict) -> ToolResult:
        """Execute a tool."""
        self.executed_tools.append((tool_type, parameters))

        # Simulate success/failure based on parameters
        if parameters.get("should_fail"):
            return ToolResult(success=False, error="Simulated failure")

        return ToolResult(success=True)
