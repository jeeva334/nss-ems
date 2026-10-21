from sqlalchemy.orm import Session

from app.core.logging import correlation_id_var
from app.models import AuditLog


def record(db: Session, action: str, actor_id: int | None = None, target_type: str | None = None,
           target_id: int | str | None = None, meta: dict | None = None) -> None:
    """Adds an audit row to the caller's transaction. Callers must never pass secrets in meta."""
    cid = correlation_id_var.get()
    db.add(AuditLog(actor_user_id=actor_id, action=action, target_type=target_type,
                    target_id=None if target_id is None else str(target_id),
                    meta=meta or {}, correlation_id=None if cid == "-" else cid))
