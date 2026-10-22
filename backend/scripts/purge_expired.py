"""Housekeeping, safe to run from cron / a scheduled job:  python -m scripts.purge_expired
Deletes expired/revoked sessions (older than 7 days) and old rate-limit counters. Audit logs and invitations are kept."""
from sqlalchemy import text

from app.db.session import engine

with engine.begin() as c:
    s = c.execute(text("DELETE FROM sessions WHERE COALESCE(revoked_at, expires_at) < now() - interval '7 days'")).rowcount
    r = c.execute(text("DELETE FROM rate_limit_events WHERE created_at < now() - interval '1 day'")).rowcount
print(f"purged sessions={s} rate_limit_events={r}")
