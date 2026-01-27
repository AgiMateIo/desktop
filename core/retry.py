"""Retry utilities with exponential backoff.

Provides retry decorator for async functions with configurable backoff strategy.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Callable, TypeVar, Any
from functools import wraps

import aiohttp


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


def _is_transient_error(exception: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.

    Transient errors:
    - Network errors (ConnectionError, TimeoutError)
    - HTTP 5xx errors (server errors)
    - aiohttp client errors (network issues)

    Non-transient errors (fail fast):
    - HTTP 4xx errors (client errors - bad request, auth, not found)
    - ValueError, TypeError (programming errors)
    """
    # Network/timeout errors - always retry
    if isinstance(exception, (ConnectionError, asyncio.TimeoutError, TimeoutError)):
        return True

    # aiohttp errors
    if isinstance(exception, aiohttp.ClientError):
        # Server errors (5xx) are transient
        if isinstance(exception, aiohttp.ClientResponseError):
            return exception.status >= 500
        # Other network errors are transient
        return True

    # Programming errors - don't retry
    if isinstance(exception, (ValueError, TypeError, KeyError)):
        return False

    # Unknown errors - don't retry by default
    return False


def retry_async(config: RetryConfig = None) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        config: RetryConfig instance with retry parameters

    Example:
        @retry_async(RetryConfig(max_attempts=3, initial_delay=1.0))
        async def fetch_data():
            return await client.get("/api/data")
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    error_msg = f"{type(e).__name__}: {e!r}"

                    # Check if we should retry
                    if not _is_transient_error(e):
                        logger.warning(
                            f"{func.__name__} failed with non-transient error: {error_msg}"
                        )
                        raise

                    # Last attempt - don't wait, just raise
                    if attempt >= config.max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {config.max_attempts} attempts: {error_msg}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.initial_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )

                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay = delay * (0.5 + random.random() * 0.5)

                    logger.info(
                        f"{func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                        f"retrying in {delay:.2f}s: {error_msg}"
                    )

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator
