from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.constants import ADMIN
from app.db.session import get_db
from app.models import AuditLog, User
from app.schemas.audit import AuditListOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditListOut)
def list_audit_logs(action: str | None = Query(None, max_length=60, description="Action prefix, e.g. 'auth.'"),
                    actor_user_id: int | None = None, target_type: str | None = Query(None, max_length=40),
                    target_id: str | None = Query(None, max_length=40),
                    date_from: datetime | None = None, date_to: datetime | None = None,
                    page: int = Query(1, ge=1, le=100000), page_size: int = Query(25, ge=1, le=100),
                    db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    stmt = select(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_user_id)
    if action:
        esc = action.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(AuditLog.action.ilike(esc + "%", escape="\\"))
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    if date_from:
        stmt = stmt.where(AuditLog.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.timestamp <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{"id": a.id, "timestamp": a.timestamp, "action": a.action, "target_type": a.target_type,
              "target_id": a.target_id, "metadata": a.meta, "correlation_id": a.correlation_id,
              "actor": None if u is None else {"id": u.id, "employee_id": u.employee_id, "full_name": u.full_name}}
             for a, u in rows]
    return AuditListOut(items=items, total=total, page=page, page_size=page_size)
