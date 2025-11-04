"""
Circuit breaker pattern for reliability and fault tolerance.

Prevents cascading failures when dependencies fail.
"""

import time
from enum import Enum
from functools import wraps
from threading import Lock
from typing import Callable, Optional


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing - reject requests immediately
    HALF_OPEN = "half_open"  # Testing - allow limited requests


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open (dependency unavailable)."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open. Service temporarily unavailable. "
            f"Retry after {retry_after:.1f} seconds"
        )


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, reject all requests immediately
    - HALF_OPEN: After timeout, allow limited requests to test recovery

    Use cases:
    - External API calls (sentiment model, embeddings)
    - Database connections (SQLite, vector DB)
    - File system operations

    Benefits:
    - Fast failure (no waiting for timeouts)
    - Automatic recovery testing
    - Prevents resource exhaustion
    - Zero-cost (no external service)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: str = "circuit_breaker",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that counts as failure
            name: Circuit breaker name (for logging)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    def _record_success(self) -> None:
        """Record successful call."""
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        """Record failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def _check_recovery(self) -> None:
        """Check if circuit should enter half-open state."""
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._last_failure_time is not None
            ):
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._failure_count = 0

    def call(self, func: Callable, *args, **kwargs):
        """
        Call function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: If function raises exception
        """
        # Check if recovery should be attempted
        self._check_recovery()

        # Check circuit state
        if self._state == CircuitState.OPEN:
            retry_after = self.recovery_timeout
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                retry_after = max(0, self.recovery_timeout - elapsed)
            raise CircuitBreakerOpen(retry_after)

        # Try to call function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e

    def __call__(self, func: Callable) -> Callable:
        """
        Use as decorator.

        Usage:
            breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

            @breaker
            def call_external_api():
                return requests.get("https://api.example.com")
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
