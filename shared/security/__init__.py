"""
Shared security library for defense-in-depth protection.

Provides:
- Multi-layer XSS protection (6 layers)
- Excel formula injection prevention
- Token bucket rate limiting (in-memory, $0 cost)
- Circuit breaker pattern for reliability
- File validation and sanitization

Based on real production threats: 16% of records contain injection attacks.
"""

from .sanitizer import XSSProtection, ExcelFormulaProtection, sanitize_text
from .rate_limiter import TokenBucketRateLimiter, RateLimitExceeded
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .validators import FileValidator, FileValidationError

__all__ = [
    "XSSProtection",
    "ExcelFormulaProtection",
    "sanitize_text",
    "TokenBucketRateLimiter",
    "RateLimitExceeded",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "FileValidator",
    "FileValidationError",
]
