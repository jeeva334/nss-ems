from datetime import datetime

from pydantic import BaseModel


class AuditActor(BaseModel):
    id: int
    employee_id: str
    full_name: str


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    actor: AuditActor | None
    action: str
    target_type: str | None
    target_id: str | None
    metadata: dict
    correlation_id: str | None


class AuditListOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
