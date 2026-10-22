import hashlib
import random

from sqlalchemy import text

from app.core.errors import AppError
from app.db.session import engine


def _h(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class FailureLimiter:
    """Sliding-window limiter shared by ALL workers/instances through PostgreSQL.
    Each call uses its own short transaction, so recorded failures survive a rolled-back request.
    Counting is approximate under simultaneous bursts (check-then-insert), which is acceptable for brute-force defence."""

    def check(self, key: str, max_hits: int, window: int) -> None:
        with engine.begin() as c:
            n = c.execute(text("SELECT count(*) FROM rate_limit_events WHERE key_hash = :k "
                               "AND created_at > now() - make_interval(secs => :w)"), {"k": _h(key), "w": window}).scalar()
        if n >= max_hits:
            raise AppError(429, "rate_limited", "Too many attempts. Please try again later.")

    def hit(self, key: str, window: int) -> None:
        with engine.begin() as c:
            c.execute(text("INSERT INTO rate_limit_events (key_hash) VALUES (:k)"), {"k": _h(key)})
            if random.random() < 0.01:  # opportunistic cleanup; scripts/purge_expired.py does the full sweep
                c.execute(text("DELETE FROM rate_limit_events WHERE created_at < now() - interval '1 day'"))

    def clear(self, key: str) -> None:
        with engine.begin() as c:
            c.execute(text("DELETE FROM rate_limit_events WHERE key_hash = :k"), {"k": _h(key)})

    def reset(self) -> None:
        with engine.begin() as c:
            c.execute(text("DELETE FROM rate_limit_events"))


limiter = FailureLimiter()
