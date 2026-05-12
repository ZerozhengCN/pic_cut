"""Retry decorators for Vertex API calls."""
from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

try:
    from google.api_core import exceptions as gax

    _RETRYABLE = (
        gax.ResourceExhausted,
        gax.ServiceUnavailable,
        gax.DeadlineExceeded,
        gax.InternalServerError,
        gax.GatewayTimeout,
    )
except ImportError:
    _RETRYABLE = (TimeoutError, ConnectionError)


retry_api = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
