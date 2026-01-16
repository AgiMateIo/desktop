"""TTS action plugin using system tools."""

import asyncio
import logging
import platform
import shutil
from pathlib import Path
from typing import Any

from core.plugin_base import ActionPlugin

logger = logging.getLogger(__name__)


class TTSAction(ActionPlugin):
    """Action plugin for text-to-speech using system tools."""

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
    def status(self) -> str:
        """Return status with availability info."""
        if not self._enabled:
            return "Disabled"
        if not self._tts_available:
            return "No TTS tool found"
        return "Running"

    def get_supported_actions(self) -> list[str]:
        return ["TTS", "TTS_STOP"]

    async def initialize(self) -> None:
        """Initialize and detect system TTS tool."""
        self._detect_tts_tool()

        if self._tts_available:
            logger.info(f"TTS initialized with: {self._tts_command}")
        else:
            logger.warning(f"No TTS tool found for {self._system}")

    def _detect_tts_tool(self) -> None:
        """Detect available system TTS tool."""
        if self._system == "Darwin":
            # macOS: use 'say' command
            if shutil.which("say"):
                self._tts_command = "say"
                self._tts_available = True

        elif self._system == "Linux":
            # Linux: try espeak, then spd-say
            if shutil.which("espeak"):
                self._tts_command = "espeak"
                self._tts_available = True
            elif shutil.which("spd-say"):
                self._tts_command = "spd-say"
                self._tts_available = True

        elif self._system == "Windows":
            # Windows: PowerShell with SAPI is always available
            self._tts_command = "powershell"
            self._tts_available = True

    async def shutdown(self) -> None:
        """Shutdown and stop any running speech."""
        await self._stop()
        logger.info("TTS shutdown")

    async def execute(self, action_type: str, parameters: dict[str, Any]) -> bool:
        """Execute a TTS action."""
        if not self._tts_available:
            logger.error("TTS not available on this system")
            return False

        if action_type == "TTS":
            return await self._speak(parameters)
        elif action_type == "TTS_STOP":
            return await self._stop()

        logger.warning(f"Unknown TTS action: {action_type}")
        return False

    async def _speak(self, parameters: dict[str, Any]) -> bool:
        """Speak the given text using system TTS."""
        text = parameters.get("text", "")
        if not text:
            logger.warning("No text provided for TTS")
            return False

        # Stop any current speech first
        await self._stop()

        try:
            if self._system == "Darwin":
                # macOS: say -v Voice "text"
                voice = parameters.get("voice", self.get_config("voice"))
                rate = parameters.get("rate", self.get_config("rate"))

                cmd = ["say"]
                if voice:
                    cmd.extend(["-v", voice])
                if rate:
                    cmd.extend(["-r", str(rate)])
                cmd.append(text)

            elif self._system == "Linux":
                if self._tts_command == "espeak":
                    # espeak -v voice -s rate "text"
                    voice = parameters.get("voice", self.get_config("voice", "en"))
                    rate = parameters.get("rate", self.get_config("rate", 150))
                    cmd = ["espeak", "-v", voice, "-s", str(rate), text]
                else:
                    # spd-say "text"
                    cmd = ["spd-say", text]

            elif self._system == "Windows":
                # PowerShell SAPI
                rate = parameters.get("rate", self.get_config("rate", 0))
                ps_script = f'''
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $synth.Rate = {rate}
                $synth.Speak("{text.replace('"', '`"')}")
                '''
                cmd = ["powershell", "-Command", ps_script]

            self._current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            await self._current_process.wait()
            self._current_process = None

            logger.info(f"TTS spoke: {text[:50]}...")
            return True

        except Exception as e:
            logger.error(f"TTS speak error: {e}")
            self._current_process = None
            return False

    async def _stop(self) -> bool:
        """Stop current speech."""
        if self._current_process:
            try:
                self._current_process.terminate()
                await self._current_process.wait()
                self._current_process = None
                logger.info("TTS stopped")
            except Exception as e:
                logger.error(f"TTS stop error: {e}")
                return False
        return True
