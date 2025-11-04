"""
Token bucket rate limiting (in-memory, $0 cost).

No external service required (no Redis, no cloud service).
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.1f} seconds")


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter (in-memory implementation).

    Features:
    - Smooth rate limiting (not bursty)
    - Per-key tracking (IP, user, API key)
    - Thread-safe
    - Zero-cost (no external service)
    - Automatic cleanup of old entries

    Algorithm:
    - Each key gets a bucket with max_tokens capacity
    - Tokens refill at refill_rate tokens/second
    - Each request consumes 1 token
    - Request blocked if bucket empty

    Example:
        # Allow 10 requests/minute per IP
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=10/60)
        limiter.check("192.168.1.1")  # Raises RateLimitExceeded if exceeded
    """

    def __init__(
        self,
        max_tokens: int = 100,
        refill_rate: float = 10.0,
        cleanup_interval: int = 3600,
    ):
        """
        Initialize rate limiter.

        Args:
            max_tokens: Maximum tokens in bucket (burst capacity)
            refill_rate: Tokens added per second
            cleanup_interval: Seconds before cleaning up inactive keys
        """
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.cleanup_interval = cleanup_interval

        # key -> (tokens, last_update_time)
        self._buckets: Dict[str, Tuple[float, float]] = defaultdict(
            lambda: (max_tokens, time.time())
        )
        self._lock = Lock()

    def _refill_bucket(self, key: str) -> float:
        """Refill bucket based on elapsed time since last update."""
        tokens, last_update = self._buckets[key]
        now = time.time()
        elapsed = now - last_update

        # Add tokens based on elapsed time
        tokens = min(self.max_tokens, tokens + elapsed * self.refill_rate)

        # Update bucket
        self._buckets[key] = (tokens, now)
        return tokens

    def check(self, key: str, tokens_required: int = 1) -> None:
        """
        Check if request is allowed (raises RateLimitExceeded if not).

        Args:
            key: Identifier (IP address, user ID, API key)
            tokens_required: Number of tokens to consume (default: 1)

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        with self._lock:
            # Refill bucket
            tokens = self._refill_bucket(key)

            # Check if enough tokens
            if tokens >= tokens_required:
                # Consume tokens
                tokens -= tokens_required
                now = time.time()
                self._buckets[key] = (tokens, now)
            else:
                # Rate limit exceeded - calculate retry_after
                tokens_needed = tokens_required - tokens
                retry_after = tokens_needed / self.refill_rate
                raise RateLimitExceeded(retry_after)

    def check_allowed(self, key: str, tokens_required: int = 1) -> bool:
        """
        Check if request is allowed (returns bool instead of raising).

        Args:
            key: Identifier (IP address, user ID, API key)
            tokens_required: Number of tokens to consume (default: 1)

        Returns:
            True if allowed, False if rate limited
        """
        try:
            self.check(key, tokens_required)
            return True
        except RateLimitExceeded:
            return False

    def cleanup(self) -> int:
        """
        Remove inactive keys to prevent memory leak.

        Returns:
            Number of keys removed
        """
        with self._lock:
            now = time.time()
            keys_to_remove = [
                key
                for key, (tokens, last_update) in self._buckets.items()
                if now - last_update > self.cleanup_interval
            ]

            for key in keys_to_remove:
                del self._buckets[key]

            return len(keys_to_remove)

    def reset(self, key: str) -> None:
        """Reset bucket for a specific key."""
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]

    def get_remaining_tokens(self, key: str) -> float:
        """Get remaining tokens for a key (without consuming)."""
        with self._lock:
            return self._refill_bucket(key)
