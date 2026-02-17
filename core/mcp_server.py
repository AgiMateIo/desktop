"""MCP server manager - exposes tool plugins as MCP tools via Streamable HTTP."""

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

import uvicorn

if TYPE_CHECKING:
    from core.plugin_manager import PluginManager
    from core.plugin_base import PluginEvent

logger = logging.getLogger(__name__)

_MAX_TRIGGER_QUEUE_SIZE = 100
_STARTUP_POLL_INTERVAL = 0.1
_STARTUP_TIMEOUT_SECONDS = 5


class _NoSignalServer(uvicorn.Server):
    """Uvicorn server that does not install signal handlers.

    Prevents uvicorn from overriding Qt/qasync signal handling.
    """

    @contextlib.contextmanager
    def capture_signals(self):
        yield


class MCPServerManager:
    """Manages the FastMCP HTTP server lifecycle.

    Registers all enabled ToolPlugins as MCP tools.
    Buffers trigger events for polling by MCP clients via get_pending_triggers.
    Runs uvicorn inside the existing asyncio event loop.
    """

    def __init__(
        self,
        plugin_manager: "PluginManager",
        port: int = 9999,
        host: str = "127.0.0.1",
    ):
        self._plugin_manager = plugin_manager
        self._port = port
        self._host = host
        self._server_task: asyncio.Task | None = None
        self._uvicorn_server: _NoSignalServer | None = None
        self._trigger_queue: asyncio.Queue = asyncio.Queue(
            maxsize=_MAX_TRIGGER_QUEUE_SIZE
        )
        self._running = False
        self._mcp = None

    @property
    def running(self) -> bool:
        return self._running

    def _build_mcp(self):
        """Build the FastMCP instance and register all tool plugins as MCP tools."""
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP(
            name="Agimate Desktop",
            instructions=(
                "This MCP server exposes tools installed on the local desktop agent. "
                "Use get_pending_triggers to receive trigger events emitted by the agent."
            ),
        )

        capabilities = self._plugin_manager.get_capabilities()
        tools_caps = capabilities.get("tools", {})

        for tool_type, cap in tools_caps.items():
            description = cap.get("description", f"Execute {tool_type}")
            params_list = cap.get("params", [])
            mcp_tool_name = tool_type.replace(".", "_")

            def make_handler(bound_tool_type: str, bound_params: list[str]):
                async def handler(parameters: str = "{}") -> str:
                    """Execute the tool with JSON parameters string."""
                    try:
                        params_dict = json.loads(parameters) if parameters else {}
                    except json.JSONDecodeError as e:
                        return json.dumps({
                            "success": False,
                            "error": f"Invalid JSON parameters: {e}",
                        })

                    result = await self._plugin_manager.execute_tool(
                        bound_tool_type, params_dict
                    )
                    return json.dumps({
                        "success": result.success,
                        "data": result.data,
                        "error": result.error,
                    })

                handler.__doc__ = (
                    f"{description}\n\n"
                    f"Parameters: JSON string with keys: "
                    f"{', '.join(bound_params) if bound_params else 'none'}.\n"
                    f"Tool type: {bound_tool_type}"
                )
                handler.__name__ = mcp_tool_name
                return handler

            tool_fn = make_handler(tool_type, params_list)
            mcp.tool(name=mcp_tool_name)(tool_fn)
            logger.info(f"Registered MCP tool: {mcp_tool_name}")

        @mcp.tool(name="get_pending_triggers")
        async def get_pending_triggers(max_count: int = 10) -> str:
            """Drain buffered trigger events from the desktop agent.

            Returns a JSON array of trigger events that have fired since the last poll.
            Each event has: plugin_id, event_name, data.
            Returns empty array when no triggers are pending.

            Args:
                max_count: Maximum number of events to return (default 10, max 100).
            """
            max_count = min(max(1, max_count), 100)
            events = []
            for _ in range(max_count):
                try:
                    event = self._trigger_queue.get_nowait()
                    events.append(event)
                except asyncio.QueueEmpty:
                    break
            return json.dumps(events)

        return mcp

    def on_trigger(self, event: "PluginEvent") -> None:
        """Handle a plugin trigger event - buffer for MCP client polling.

        Called synchronously from EventBus.
        Drops oldest event if queue is full.
        """
        event_data = {
            "plugin_id": event.plugin_id,
            "event_name": event.event_name,
            "data": event.data,
        }
        try:
            self._trigger_queue.put_nowait(event_data)
        except asyncio.QueueFull:
            try:
                self._trigger_queue.get_nowait()
                self._trigger_queue.put_nowait(event_data)
                logger.warning("Trigger queue full, dropped oldest event")
            except asyncio.QueueEmpty:
                pass

    async def start(self) -> None:
        """Start the MCP HTTP server as an asyncio background task."""
        if self._running:
            logger.warning("MCP server already running")
            return

        try:
            self._mcp = self._build_mcp()
            asgi_app = self._mcp.streamable_http_app()

            config = uvicorn.Config(
                app=asgi_app,
                host=self._host,
                port=self._port,
                log_level="warning",
                loop="none",
            )
            self._uvicorn_server = _NoSignalServer(config)

            self._server_task = asyncio.create_task(
                self._uvicorn_server.serve(),
                name="mcp-uvicorn-server",
            )

            # Wait for server to actually bind to the port
            polls = int(_STARTUP_TIMEOUT_SECONDS / _STARTUP_POLL_INTERVAL)
            for _ in range(polls):
                await asyncio.sleep(_STARTUP_POLL_INTERVAL)
                if self._uvicorn_server.started:
                    break
                if self._server_task.done():
                    exc = self._server_task.exception()
                    raise RuntimeError(f"MCP server exited during startup: {exc}")
            else:
                raise RuntimeError("MCP server startup timed out")

            self._running = True
            logger.info(
                f"MCP server started at http://{self._host}:{self._port}/mcp"
            )
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            self._mcp = None
            self._uvicorn_server = None
            if self._server_task and not self._server_task.done():
                self._server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._server_task
            self._server_task = None
            self._running = False

    async def stop(self) -> None:
        """Stop the MCP HTTP server."""
        if not self._running:
            return

        self._running = False

        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_task and not self._server_task.done():
            try:
                await asyncio.wait_for(self._server_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._server_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._server_task

        self._uvicorn_server = None
        self._server_task = None

        logger.info("MCP server stopped")
