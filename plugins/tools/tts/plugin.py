"""TTS tool plugin using system tools."""

import asyncio
import logging
import platform
import shutil
from pathlib import Path
from typing import Any

from core.plugin_base import ToolPlugin
from core.tool_types import TOOL_TTS, TOOL_TTS_STOP
from core.models import ToolResult
from core.constants import PLATFORM_MACOS, PLATFORM_LINUX, PLATFORM_WINDOWS
from core.platform_commands import MacOSCommands, LinuxCommands, WindowsCommands

logger = logging.getLogger(__name__)


class TTSTool(ToolPlugin):
    """Tool plugin for text-to-speech using system tools."""

    def __init__(self, plugin_dir: Path):
        super().__init__(plugin_dir)
        self._system = platform.system()
        self._tts_command: str | None = None
        self._tts_available = False
        self._current_process: asyncio.subprocess.Process | None = None

    @property
    def name(self) -> str:
        return "TTS"

    @property
    def description(self) -> str:
        return "Text-to-speech using system tools (say, espeak, SAPI)"

    @property
    def status(self) -> str:
        """Return status with availability info."""
        if not self.enabled:
            return "Disabled"
        if not self._tts_available:
            return "No TTS tool found"
        return "Running"

    def get_supported_tools(self) -> list[str]:
        return [TOOL_TTS, TOOL_TTS_STOP]

    def get_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return TTS tool capabilities."""
        return {
            TOOL_TTS: {
                "params": ["text", "voice", "rate"],
                "description": "Speak text aloud using system TTS",
            },
            TOOL_TTS_STOP: {
                "params": [],
                "description": "Stop current speech",
            },
        }

    async def initialize(self) -> None:
        """Initialize and detect system TTS tool."""
        self._detect_tts_tool()

        if self._tts_available:
            logger.info(f"TTS initialized with: {self._tts_command}")
        else:
            logger.warning(f"No TTS tool found for {self._system}")

    def _detect_tts_tool(self) -> None:
        """Detect available system TTS tool."""
        macos_cmds = MacOSCommands()
        linux_cmds = LinuxCommands()
        windows_cmds = WindowsCommands()

        if self._system == PLATFORM_MACOS:
            # macOS: use 'say' command
            if shutil.which(macos_cmds.SAY):
                self._tts_command = macos_cmds.SAY
                self._tts_available = True

        elif self._system == PLATFORM_LINUX:
            # Linux: try espeak, then spd-say
            if shutil.which(linux_cmds.ESPEAK):
                self._tts_command = linux_cmds.ESPEAK
                self._tts_available = True
            elif shutil.which(linux_cmds.SPD_SAY):
                self._tts_command = linux_cmds.SPD_SAY
                self._tts_available = True

        elif self._system == PLATFORM_WINDOWS:
            # Windows: PowerShell with SAPI is always available
            self._tts_command = windows_cmds.POWERSHELL
            self._tts_available = True

    async def shutdown(self) -> None:
        """Shutdown and stop any running speech."""
        await self._stop()
        logger.info("TTS shutdown")

    async def execute(self, tool_type: str, parameters: dict[str, Any]) -> ToolResult:
        """Execute a TTS tool."""
        if not self._tts_available:
            logger.error("TTS not available on this system")
            return ToolResult(success=False, error="TTS not available on this system")

        if tool_type == TOOL_TTS:
            return await self._speak(parameters)
        elif tool_type == TOOL_TTS_STOP:
            return await self._stop()

        logger.warning(f"Unknown TTS tool: {tool_type}")
        return ToolResult(success=False, error=f"Unknown tool: {tool_type}")

    async def _speak(self, parameters: dict[str, Any]) -> ToolResult:
        """Speak the given text using system TTS."""
        text = parameters.get("text", "")
        if not text:
            logger.warning("No text provided for TTS")
            return ToolResult(success=False, error="No text provided")

        # Stop any current speech first
        await self._stop()

        try:
            macos_cmds = MacOSCommands()
            linux_cmds = LinuxCommands()
            windows_cmds = WindowsCommands()

            if self._system == PLATFORM_MACOS:
                # macOS: say -v Voice "text"
                voice = parameters.get("voice", self.get_config("voice"))
                rate = parameters.get("rate", self.get_config("rate"))

                cmd = [macos_cmds.SAY]
                if voice:
                    cmd.extend([macos_cmds.SAY_VOICE_FLAG, voice])
                if rate:
                    cmd.extend([macos_cmds.SAY_RATE_FLAG, str(rate)])
                cmd.append(text)

            elif self._system == PLATFORM_LINUX:
                if self._tts_command == linux_cmds.ESPEAK:
                    # espeak -v voice -s rate "text"
                    voice = parameters.get("voice", self.get_config("voice", "en"))
                    rate = parameters.get("rate", self.get_config("rate", 150))
                    cmd = [linux_cmds.ESPEAK, "-v", voice, "-s", str(rate), text]
                else:
                    # spd-say "text"
                    cmd = [linux_cmds.SPD_SAY, text]

            elif self._system == PLATFORM_WINDOWS:
                # PowerShell SAPI
                rate = parameters.get("rate", self.get_config("rate", 0))
                ps_script = f'''
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $synth.Rate = {rate}
                $synth.Speak("{text.replace('"', '`"')}")
                '''
                cmd = [windows_cmds.POWERSHELL, windows_cmds.POWERSHELL_COMMAND_FLAG, ps_script]

            self._current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            await self._current_process.wait()
            self._current_process = None

            logger.info(f"TTS spoke: {text[:50]}...")
            return ToolResult(success=True)

        except Exception as e:
            logger.error(f"TTS speak error: {e}")
            self._current_process = None
            return ToolResult(success=False, error=str(e))

    async def _stop(self) -> ToolResult:
        """Stop current speech."""
        if self._current_process:
            try:
                self._current_process.terminate()
                await self._current_process.wait()
                self._current_process = None
                logger.info("TTS stopped")
            except Exception as e:
                logger.error(f"TTS stop error: {e}")
                return ToolResult(success=False, error=str(e))
        return ToolResult(success=True)
