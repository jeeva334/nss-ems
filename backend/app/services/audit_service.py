import re

from sqlalchemy.orm import Session

from app.core.logging import correlation_id_var
from app.models import AuditLog

_SECRET_KEY = re.compile(r"(pass(word)?|token|secret|hash|authorization|cookie|csrf|session|api[_-]?key)", re.I)
_MAX_STR = 300


def scrub(meta: dict | None) -> dict:
    """Defence in depth: even if a caller mistakenly passes a secret, it is never persisted."""
    out = {}
    for k, v in (meta or {}).items():
        if _SECRET_KEY.search(str(k)):
            out[k] = "[redacted]"
        elif isinstance(v, dict):
            out[k] = scrub(v)
        elif isinstance(v, str):
            out[k] = v[:_MAX_STR]
        else:
            out[k] = v
    return out


def record(db: Session, action: str, actor_id: int | None = None, target_type: str | None = None,
           target_id: int | str | None = None, meta: dict | None = None) -> None:
    """Adds an audit row to the caller's transaction."""
    cid = correlation_id_var.get()
    db.add(AuditLog(actor_user_id=actor_id, action=action, target_type=target_type,
                    target_id=None if target_id is None else str(target_id),
                    meta=scrub(meta), correlation_id=None if cid == "-" else cid))
