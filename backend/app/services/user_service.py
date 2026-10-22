from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import ACTIVE, ADMIN, INACTIVE, MANAGER, PENDING, SUPERVISOR
from app.core.errors import AppError
from app.models import Client, SupervisorAssignment, User
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit_service, auth_service, invitation_service


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "user_not_found", "User not found.")
    return user


def list_users(db: Session, q: str | None, role: str | None, status: str | None, page: int, page_size: int,
               mapped: bool | None = None):
    stmt = select(User)
    if q and q.strip():
        pat = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(or_(*(c.ilike(pat, escape="\\") for c in
                                (User.employee_id, User.full_name, User.email, User.mobile_number))))
    if role:
        stmt = stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
    if mapped is not None:  # Supervisors with / without a Manager mapping
        has = select(SupervisorAssignment.id).where(SupervisorAssignment.supervisor_id == User.id).exists()
        stmt = stmt.where(has if mapped else ~has)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(User.created_at.desc(), User.id.desc())
                       .offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_user(db: Session, data: UserCreate, actor: User):
    email = data.email.lower()
    user = User(full_name=data.full_name, email=email, mobile_number=data.mobile_number, role=data.role,
                status=PENDING, created_by_user_id=actor.id)
    try:
        db.add(user)
        db.flush()  # employee_id allocated by PostgreSQL here
        inv, token = invitation_service.issue(db, user, actor.id)
        audit_service.record(db, "user.create", actor.id, "user", user.id, {"role": user.role})
        db.commit()  # account + invitation are durable BEFORE any email is attempted
    except IntegrityError:
        db.rollback()
        raise AppError(409, "duplicate_email", "A user with this email already exists.") from None
    delivery = invitation_service.deliver(db, user, inv, token, actor.id)
    return user, inv, delivery


def update_user(db: Session, user: User, data: UserUpdate, actor: User) -> User:
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = changes["email"].lower()
    email_changed = "email" in changes and changes["email"] != user.email
    for k, v in changes.items():
        setattr(user, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "duplicate_email", "A user with this email already exists.") from None
    if email_changed and user.status == PENDING:
        invitation_service.revoke_active(db, user.id)  # old link was sent to the previous address
    audit_service.record(db, "user.update", actor.id, "user", user.id, {"fields": sorted(changes)})
    db.commit()
    return user


def set_status(db: Session, user: User, new_status: str, actor: User) -> User:
    if user.status == new_status:
        raise AppError(409, "invalid_transition", f"User is already {new_status.lower()}.")
    if new_status == INACTIVE:
        db.refresh(user, with_for_update=True)  # serialises against concurrent assignments to this user
        if user.id == actor.id:
            raise AppError(409, "cannot_deactivate_self", "You cannot deactivate your own account.")
        if user.role == ADMIN and not db.scalar(select(User.id).where(
                User.role == ADMIN, User.status == ACTIVE, User.id != user.id).limit(1)):
            raise AppError(409, "last_admin", "You cannot deactivate the last active Admin.")
        if user.role == MANAGER and (
                db.scalar(select(Client.id).where(Client.manager_id == user.id).limit(1)) is not None
                or db.scalar(select(SupervisorAssignment.id).where(SupervisorAssignment.manager_id == user.id).limit(1)) is not None):
            raise AppError(409, "has_dependent_assignments",
                           "Reassign this Manager's clients and Supervisors before deactivating.")
        user.status = INACTIVE
        if user.role == SUPERVISOR:  # recorded in history + audit; an inactive Supervisor keeps no live mapping
            from app.services import assignment_service
            assignment_service.remove_mapping_no_commit(db, user, actor.id, "supervisor_unmapped_on_deactivation")
        auth_service.revoke_user_sessions(db, user.id)
        invitation_service.revoke_active(db, user.id)
    else:
        # A never-activated account goes back to PENDING and needs a fresh invitation.
        user.status = ACTIVE if user.password_hash else PENDING
    audit_service.record(db, "user.status_change", actor.id, "user", user.id, {"to": user.status})
    db.commit()
    return user


def assignments_for(db: Session, user: User) -> dict:
    if user.role == MANAGER:
        clients = db.execute(select(Client.id, Client.client_code, Client.client_name, Client.status)
                             .where(Client.manager_id == user.id).order_by(Client.client_name)).all()
        sups = db.execute(select(User.id, User.employee_id, User.full_name, SupervisorAssignment.client_id)
                          .join(SupervisorAssignment, SupervisorAssignment.supervisor_id == User.id)
                          .where(SupervisorAssignment.manager_id == user.id).order_by(User.full_name)).all()
        return {"clients": [dict(r._mapping) for r in clients], "supervisors": [dict(r._mapping) for r in sups]}
    if user.role == SUPERVISOR:
        a = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == user.id))
        if a is None:
            return {"manager": None, "client": None}
        mgr = db.get(User, a.manager_id)
        cl = db.get(Client, a.client_id) if a.client_id else None
        return {"manager": {"id": mgr.id, "employee_id": mgr.employee_id, "full_name": mgr.full_name},
                "client": {"id": cl.id, "client_code": cl.client_code, "client_name": cl.client_name} if cl else None}
    return {}
