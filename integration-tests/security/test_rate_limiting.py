"""
Rate limiting security tests.
"""

import time

import pytest

from shared.security import TokenBucketRateLimiter, RateLimitExceeded


class TestRateLimiting:
    """Test token bucket rate limiter."""

    def test_allows_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=10)

        # Should allow 10 requests immediately
        for i in range(10):
            limiter.check(f"user-1")  # Should not raise

    def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limiter = TokenBucketRateLimiter(max_tokens=5, refill_rate=1)

        # Use up all tokens
        for i in range(5):
            limiter.check("user-1")

        # Next request should be blocked
        with pytest.raises(RateLimitExceeded) as exc_info:
            limiter.check("user-1")

        assert exc_info.value.retry_after > 0

    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = TokenBucketRateLimiter(max_tokens=5, refill_rate=10)  # 10 tokens/sec

        # Use up all tokens
        for i in range(5):
            limiter.check("user-1")

        # Wait for refill (100ms = 1 token at 10/sec)
        time.sleep(0.15)  # 150ms = ~1.5 tokens

        # Should allow 1 more request
        limiter.check("user-1")  # Should not raise

    def test_per_key_isolation(self):
        """Test that different keys have separate buckets."""
        limiter = TokenBucketRateLimiter(max_tokens=5, refill_rate=1)

        # Use up tokens for user-1
        for i in range(5):
            limiter.check("user-1")

        # user-1 should be blocked
        with pytest.raises(RateLimitExceeded):
            limiter.check("user-1")

        # user-2 should still have tokens
        limiter.check("user-2")  # Should not raise

    def test_check_allowed_method(self):
        """Test check_allowed method (returns bool instead of raising)."""
        limiter = TokenBucketRateLimiter(max_tokens=3, refill_rate=1)

        # Should allow first 3
        assert limiter.check_allowed("user-1") is True
        assert limiter.check_allowed("user-1") is True
        assert limiter.check_allowed("user-1") is True

        # Should block 4th
        assert limiter.check_allowed("user-1") is False

    def test_cleanup(self):
        """Test cleanup of inactive keys."""
        limiter = TokenBucketRateLimiter(
            max_tokens=10, refill_rate=1, cleanup_interval=1
        )

        # Create 10 keys
        for i in range(10):
            limiter.check(f"user-{i}")

        # Wait for cleanup interval
        time.sleep(1.1)

        # Cleanup should remove inactive keys
        removed = limiter.cleanup()
        assert removed > 0

    def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        import threading

        limiter = TokenBucketRateLimiter(max_tokens=100, refill_rate=100)

        success_count = [0]
        lock = threading.Lock()

        def make_request():
            try:
                limiter.check("shared-user")
                with lock:
                    success_count[0] += 1
            except RateLimitExceeded:
                pass

        # Create 150 threads (should exceed limit)
        threads = [threading.Thread(target=make_request) for _ in range(150)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should allow ~100 requests (max_tokens)
        # Some variance due to timing
        assert 90 <= success_count[0] <= 110


class TestRateLimitingIntegration:
    """Test rate limiting integration with API."""

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self):
        """
        Test rate limiting in API context.

        This would test FastAPI integration,
        but requires running server.
        """
        # TODO: Implement with httpx TestClient
        pass
