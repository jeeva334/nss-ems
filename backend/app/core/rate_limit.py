import threading
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class FailureLimiter:
    """In-process sliding-window limiter. Per worker only: documented limitation
    (swap for a DB/Redis-backed implementation when running multiple instances)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: int) -> deque:
        q, now = self._hits[key], time.monotonic()
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key: str, max_hits: int, window: int) -> None:
        with self._lock:
            if len(self._prune(key, window)) >= max_hits:
                raise AppError(429, "rate_limited", "Too many attempts. Please try again later.")

    def hit(self, key: str, window: int) -> None:
        with self._lock:
            self._prune(key, window).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = FailureLimiter()
