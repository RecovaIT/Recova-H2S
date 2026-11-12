"""Simple in-process sliding-window rate limiter.

Adequate for a single API instance. For multi-instance deployments put a gateway
rate limiter (or Redis-backed limiter) in front; see docs/security.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise RateLimited("Too many requests, please slow down", details={"retry_after_seconds": int(window_seconds - (now - q[0])) + 1})
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
