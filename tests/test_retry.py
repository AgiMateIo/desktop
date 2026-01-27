"""Tests for retry utilities."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import aiohttp

from core.retry import RetryConfig, retry_async, _is_transient_error


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self):
        config = RetryConfig(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


class TestIsTransientError:
    """Tests for _is_transient_error function."""

    def test_connection_error_is_transient(self):
        assert _is_transient_error(ConnectionError()) is True

    def test_timeout_error_is_transient(self):
        assert _is_transient_error(TimeoutError()) is True

    def test_asyncio_timeout_error_is_transient(self):
        assert _is_transient_error(asyncio.TimeoutError()) is True

    def test_aiohttp_client_error_is_transient(self):
        assert _is_transient_error(aiohttp.ClientError()) is True

    def test_aiohttp_5xx_error_is_transient(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=500
        )
        assert _is_transient_error(error) is True

    def test_aiohttp_503_error_is_transient(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=503
        )
        assert _is_transient_error(error) is True

    def test_aiohttp_4xx_error_is_not_transient(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=404
        )
        assert _is_transient_error(error) is False

    def test_aiohttp_401_error_is_not_transient(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=401
        )
        assert _is_transient_error(error) is False

    def test_value_error_is_not_transient(self):
        assert _is_transient_error(ValueError()) is False

    def test_type_error_is_not_transient(self):
        assert _is_transient_error(TypeError()) is False

    def test_key_error_is_not_transient(self):
        assert _is_transient_error(KeyError()) is False

    def test_unknown_error_is_not_transient(self):
        assert _is_transient_error(RuntimeError()) is False


class TestRetryAsyncDecorator:
    """Tests for retry_async decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        mock_func = AsyncMock(return_value="success")
        decorated = retry_async()(mock_func)

        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_second_try(self):
        mock_func = AsyncMock(side_effect=[ConnectionError(), "success"])
        config = RetryConfig(initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_third_try(self):
        mock_func = AsyncMock(
            side_effect=[ConnectionError(), TimeoutError(), "success"]
        )
        config = RetryConfig(initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        result = await decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_attempts(self):
        mock_func = AsyncMock(side_effect=ConnectionError("network error"))
        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        with pytest.raises(ConnectionError, match="network error"):
            await decorated()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_non_transient_error_fails_immediately(self):
        mock_func = AsyncMock(side_effect=ValueError("bad value"))
        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        with pytest.raises(ValueError, match="bad value"):
            await decorated()

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_http_404_fails_immediately(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=404,
            message="Not Found"
        )
        mock_func = AsyncMock(side_effect=error)
        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        with pytest.raises(aiohttp.ClientResponseError):
            await decorated()

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_http_500_retries(self):
        error = aiohttp.ClientResponseError(
            request_info=None,
            history=None,
            status=500
        )
        mock_func = AsyncMock(side_effect=error)
        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        decorated = retry_async(config)(mock_func)

        with pytest.raises(aiohttp.ClientResponseError):
            await decorated()

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        mock_func = AsyncMock(side_effect=ConnectionError())
        config = RetryConfig(
            max_attempts=4,
            initial_delay=0.1,
            exponential_base=2.0,
            jitter=False
        )
        decorated = retry_async(config)(mock_func)

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ConnectionError):
                await decorated()

            # Should sleep with exponential backoff: 0.1, 0.2, 0.4
            assert mock_sleep.call_count == 3
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls[0] == pytest.approx(0.1, rel=0.01)
            assert calls[1] == pytest.approx(0.2, rel=0.01)
            assert calls[2] == pytest.approx(0.4, rel=0.01)

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        mock_func = AsyncMock(side_effect=ConnectionError())
        config = RetryConfig(
            max_attempts=5,
            initial_delay=10.0,
            max_delay=15.0,
            exponential_base=2.0,
            jitter=False
        )
        decorated = retry_async(config)(mock_func)

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ConnectionError):
                await decorated()

            # Should cap at max_delay: 10, 15, 15, 15
            assert mock_sleep.call_count == 4
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls[0] == pytest.approx(10.0, rel=0.01)
            assert calls[1] == pytest.approx(15.0, rel=0.01)
            assert calls[2] == pytest.approx(15.0, rel=0.01)
            assert calls[3] == pytest.approx(15.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        mock_func = AsyncMock(side_effect=ConnectionError())
        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            jitter=True
        )
        decorated = retry_async(config)(mock_func)

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ConnectionError):
                await decorated()

            # With jitter, delays should be 50-100% of calculated value
            assert mock_sleep.call_count == 2
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            # First delay: 1.0 * jitter (0.5-1.0)
            assert 0.5 <= calls[0] <= 1.0
            # Second delay: 2.0 * jitter (1.0-2.0)
            assert 1.0 <= calls[1] <= 2.0

    @pytest.mark.asyncio
    async def test_no_jitter(self):
        mock_func = AsyncMock(side_effect=ConnectionError())
        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            jitter=False
        )
        decorated = retry_async(config)(mock_func)

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ConnectionError):
                await decorated()

            # Without jitter, delays should be exact
            assert mock_sleep.call_count == 2
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls[0] == pytest.approx(1.0, rel=0.01)
            assert calls[1] == pytest.approx(2.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_preserves_function_return_value(self):
        mock_func = AsyncMock(return_value={"key": "value"})
        decorated = retry_async()(mock_func)

        result = await decorated()

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_preserves_function_args(self):
        mock_func = AsyncMock(return_value="success")
        decorated = retry_async()(mock_func)

        await decorated("arg1", "arg2", kwarg1="value1")

        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_default_config(self):
        mock_func = AsyncMock(side_effect=ConnectionError())
        decorated = retry_async()(mock_func)

        with pytest.raises(ConnectionError):
            await decorated()

        # Default config has 3 attempts
        assert mock_func.call_count == 3


class TestRetryIntegration:
    """Integration tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_realistic_network_retry_scenario(self):
        """Simulate realistic network failure followed by success."""
        call_count = 0

        @retry_async(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def flaky_network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network unavailable")
            return {"status": "ok", "data": [1, 2, 3]}

        result = await flaky_network_call()

        assert result == {"status": "ok", "data": [1, 2, 3]}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_permanent_failure_scenario(self):
        """Simulate permanent failure that exhausts retries."""

        @retry_async(RetryConfig(max_attempts=2, initial_delay=0.01))
        async def always_fails():
            raise TimeoutError("Server not responding")

        with pytest.raises(TimeoutError, match="Server not responding"):
            await always_fails()

    @pytest.mark.asyncio
    async def test_client_error_no_retry_scenario(self):
        """Simulate client error that should not retry."""

        @retry_async(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def bad_request():
            error = aiohttp.ClientResponseError(
                request_info=None,
                history=None,
                status=400,
                message="Bad Request"
            )
            raise error

        with pytest.raises(aiohttp.ClientResponseError):
            await bad_request()
