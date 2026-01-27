"""Tests for TTS action plugin."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from .plugin import TTSAction


class TestTTSInit:
    """Test cases for TTSAction initialization."""

    def test_init(self, tmp_path):
        """Test TTSAction initialization."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        plugin = TTSAction(plugin_dir)

        assert plugin.plugin_dir == plugin_dir
        assert plugin.plugin_id == "tts"
        assert plugin.name == "TTS"
        assert plugin._tts_command is None
        assert plugin._tts_available is False
        assert plugin._current_process is None

    def test_get_supported_actions(self, tmp_path):
        """Test get_supported_actions() returns correct actions."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        plugin = TTSAction(plugin_dir)

        actions = plugin.get_supported_actions()

        assert "TTS" in actions
        assert "TTS_STOP" in actions
        assert len(actions) == 2


class TestTTSDetection:
    """Test cases for TTS tool detection."""

    @pytest.mark.asyncio
    async def test_detect_macos_say(self, tmp_path, monkeypatch):
        """Test TTS detection on macOS with 'say' command."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        # Mock macOS
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say" if cmd == "say" else None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is True
        assert plugin._tts_command == "say"

    @pytest.mark.asyncio
    async def test_detect_linux_espeak(self, tmp_path, monkeypatch):
        """Test TTS detection on Linux with espeak."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        # Mock Linux with espeak
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak" if cmd == "espeak" else None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is True
        assert plugin._tts_command == "espeak"

    @pytest.mark.asyncio
    async def test_detect_linux_spd_say(self, tmp_path, monkeypatch):
        """Test TTS detection on Linux with spd-say."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        # Mock Linux with spd-say (no espeak)
        def mock_which(cmd):
            if cmd == "spd-say":
                return "/usr/bin/spd-say"
            return None

        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", mock_which)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is True
        assert plugin._tts_command == "spd-say"

    @pytest.mark.asyncio
    async def test_detect_windows(self, tmp_path, monkeypatch):
        """Test TTS detection on Windows (always available via PowerShell)."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        # Mock Windows
        monkeypatch.setattr("platform.system", lambda: "Windows")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is True
        assert plugin._tts_command == "powershell"

    @pytest.mark.asyncio
    async def test_detect_no_tts_tool(self, tmp_path, monkeypatch):
        """Test TTS detection when no tool is available."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        # Mock Linux with no TTS tools
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is False
        assert plugin._tts_command is None


class TestTTSStatus:
    """Test cases for TTS availability."""

    @pytest.mark.asyncio
    async def test_tts_available_flag(self, tmp_path, monkeypatch):
        """Test _tts_available flag when TTS is detected."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is True

    @pytest.mark.asyncio
    async def test_tts_not_available_flag(self, tmp_path, monkeypatch):
        """Test _tts_available flag when TTS is not detected."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        assert plugin._tts_available is False


class TestTTSExecution:
    """Test cases for TTS execution."""

    @pytest.mark.asyncio
    async def test_execute_tts_success(self, tmp_path, monkeypatch):
        """Test execute() with TTS action."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await plugin.execute("TTS", {"text": "Hello world"})

        assert result is True

    @pytest.mark.asyncio
    async def test_execute_tts_without_tts_available(self, tmp_path, monkeypatch):
        """Test execute() when TTS is not available."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        result = await plugin.execute("TTS", {"text": "Hello"})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_tts_without_text(self, tmp_path, monkeypatch):
        """Test execute() without text parameter."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        result = await plugin.execute("TTS", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_tts_with_empty_text(self, tmp_path, monkeypatch):
        """Test execute() with empty text."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        result = await plugin.execute("TTS", {"text": ""})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_tts_stop(self, tmp_path, monkeypatch):
        """Test execute() with TTS_STOP action."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Mock current process
        mock_process = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()
        plugin._current_process = mock_process

        result = await plugin.execute("TTS_STOP", {})

        assert result is True
        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, tmp_path, monkeypatch):
        """Test execute() with unknown action type."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        result = await plugin.execute("UNKNOWN_ACTION", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_tts_handles_exception(self, tmp_path, monkeypatch):
        """Test execute() handles subprocess exceptions."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Mock subprocess to raise exception
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Test error")):
            result = await plugin.execute("TTS", {"text": "Hello"})

        assert result is False


class TestTTSVoiceAndRate:
    """Test cases for voice and rate configuration."""

    @pytest.mark.asyncio
    async def test_macos_with_voice(self, tmp_path, monkeypatch):
        """Test macOS TTS with voice parameter."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await plugin.execute("TTS", {
                "text": "Hello",
                "voice": "Samantha",
                "rate": 200
            })

            # Verify command includes voice and rate
            call_args = mock_exec.call_args[0]
            assert "say" in call_args
            assert "-v" in call_args
            assert "Samantha" in call_args
            assert "-r" in call_args
            assert "200" in call_args

    @pytest.mark.asyncio
    async def test_linux_espeak_with_voice_and_rate(self, tmp_path, monkeypatch):
        """Test Linux espeak with voice and rate."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak" if cmd == "espeak" else None)

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await plugin.execute("TTS", {
                "text": "Hello",
                "voice": "en-us",
                "rate": 180
            })

            call_args = mock_exec.call_args[0]
            assert "espeak" in call_args
            assert "-v" in call_args
            assert "en-us" in call_args
            assert "-s" in call_args
            assert "180" in call_args

    @pytest.mark.asyncio
    async def test_windows_with_rate(self, tmp_path, monkeypatch):
        """Test Windows TTS with rate."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Windows")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await plugin.execute("TTS", {
                "text": "Hello",
                "rate": 2
            })

            call_args = mock_exec.call_args[0]
            assert "powershell" in call_args

    @pytest.mark.asyncio
    async def test_voice_from_config(self, tmp_path, monkeypatch):
        """Test using voice from config."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        config = {
            "enabled": True,
            "voice": "Alex",
            "rate": 180
        }
        (plugin_dir / "config.json").write_text(json.dumps(config))

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        plugin.load_config()
        await plugin.initialize()

        mock_process = AsyncMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            await plugin.execute("TTS", {"text": "Hello"})

            call_args = mock_exec.call_args[0]
            assert "Alex" in call_args
            assert "180" in call_args


class TestTTSShutdown:
    """Test cases for shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, tmp_path, monkeypatch):
        """Test shutdown() stops any running speech."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Mock current process
        mock_process = AsyncMock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()
        plugin._current_process = mock_process

        await plugin.shutdown()

        mock_process.terminate.assert_called_once()
        assert plugin._current_process is None

    @pytest.mark.asyncio
    async def test_shutdown_without_process(self, tmp_path, monkeypatch):
        """Test shutdown() when no process is running."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Should not crash
        await plugin.shutdown()


class TestTTSStopBehavior:
    """Test cases for stop behavior."""

    @pytest.mark.asyncio
    async def test_speak_stops_current_speech(self, tmp_path, monkeypatch):
        """Test that speaking new text stops current speech."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        # Mock first process (simulate it's still running)
        mock_process1 = AsyncMock()
        mock_process1.terminate = Mock()
        mock_process1.wait = AsyncMock()

        # Mock second process
        mock_process2 = AsyncMock()
        mock_process2.wait = AsyncMock()

        call_count = 0

        async def mock_create_subprocess(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Set as current process after creation (simulate async behavior)
                plugin._current_process = mock_process1
                # Return process but make wait() never finish (simulates running speech)
                mock_process1.wait.side_effect = asyncio.CancelledError()
                return mock_process1
            else:
                return mock_process2

        with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess):
            # Start first speech (will be interrupted)
            try:
                await plugin.execute("TTS", {"text": "First"})
            except asyncio.CancelledError:
                pass

            # Manually set current process for testing
            plugin._current_process = mock_process1

            # Start second speech (should stop first)
            await plugin.execute("TTS", {"text": "Second"})

            # First process should be terminated
            mock_process1.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_without_current_process(self, tmp_path, monkeypatch):
        """Test _stop() when no process is running."""
        plugin_dir = tmp_path / "tts"
        plugin_dir.mkdir()

        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/say")

        plugin = TTSAction(plugin_dir)
        await plugin.initialize()

        result = await plugin.execute("TTS_STOP", {})

        # Should succeed even with no process
        assert result is True
