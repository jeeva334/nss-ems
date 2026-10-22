from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import ACTIVE, ADMIN, INACTIVE, MANAGER, SUPERVISOR
from app.core.errors import AppError, forbidden
from app.models import AssignmentHistory, Client, SupervisorAssignment, User
from app.schemas.client import ClientCreate, ClientOut, ClientUpdate, PersonBrief
from app.services import audit_service
from app.services.db_guard import conflict_guard


def _like(s: str) -> str:
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def brief(u: User | None) -> dict | None:
    return None if u is None else {"id": u.id, "employee_id": u.employee_id, "full_name": u.full_name}


def to_out(c: Client, manager: User | None) -> ClientOut:
    out = ClientOut.model_validate(c)
    out.manager = PersonBrief(**brief(manager)) if manager is not None else None
    return out


def get_or_404(db: Session, client_id: int, lock: str | None = None) -> Client:
    stmt = select(Client).where(Client.id == client_id)
    if lock == "update":
        stmt = stmt.with_for_update()
    elif lock == "share":
        stmt = stmt.with_for_update(read=True)
    c = db.scalar(stmt)
    if c is None:
        raise AppError(404, "client_not_found", "Client not found.")
    return c


def supervisors_on_client(db: Session, client_id: int) -> list[dict]:
    rows = db.execute(select(User.id, User.employee_id, User.full_name)
                      .join(SupervisorAssignment, SupervisorAssignment.supervisor_id == User.id)
                      .where(SupervisorAssignment.client_id == client_id).order_by(User.full_name)).all()
    return [dict(r._mapping) for r in rows]


def assert_can_view(db: Session, actor: User, client: Client) -> None:
    """Resource-level authorization: Admin all; Manager own clients; Supervisor only their assigned client."""
    if actor.role == ADMIN:
        return
    if actor.role == MANAGER and client.manager_id == actor.id:
        return
    if actor.role == SUPERVISOR and db.scalar(select(SupervisorAssignment.id).where(
            SupervisorAssignment.supervisor_id == actor.id, SupervisorAssignment.client_id == client.id)):
        return
    raise forbidden()


def list_clients(db: Session, actor: User, q, status, manager_id, unassigned, page, page_size):
    stmt = select(Client, User).outerjoin(User, User.id == Client.manager_id)
    if actor.role == MANAGER:
        stmt = stmt.where(Client.manager_id == actor.id)  # a Manager can never list other Managers' clients
    elif manager_id is not None:
        stmt = stmt.where(Client.manager_id == manager_id)
    if unassigned:
        stmt = stmt.where(Client.manager_id.is_(None))
    if status:
        stmt = stmt.where(Client.status == status)
    if q and q.strip():
        pat = _like(q.strip())
        stmt = stmt.where(or_(Client.client_code.ilike(pat, escape="\\"), Client.client_name.ilike(pat, escape="\\")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Client.client_name, Client.id).offset((page - 1) * page_size).limit(page_size)).all()
    return [to_out(c, m) for c, m in rows], total


def create_client(db: Session, data: ClientCreate, actor: User) -> ClientOut:
    if db.scalar(select(Client.id).where(Client.client_code == data.client_code)):
        raise AppError(409, "duplicate_client_code", "A client with this code already exists.")
    c = Client(**data.model_dump(), status=ACTIVE)
    with conflict_guard(db):
        db.add(c)
        db.flush()
        audit_service.record(db, "client.create", actor.id, "client", c.id, {"client_code": c.client_code})
        db.commit()
    return to_out(c, None)


def update_client(db: Session, client: Client, data: ClientUpdate, actor: User) -> ClientOut:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise AppError(422, "validation_error", "Provide at least one field to update.")
    if "client_name" in changes and changes["client_name"] is None:
        raise AppError(422, "validation_error", "Client name cannot be empty.")
    for k, v in changes.items():
        setattr(client, k, v)
    audit_service.record(db, "client.update", actor.id, "client", client.id, {"fields": sorted(changes)})
    db.commit()
    return to_out(client, db.get(User, client.manager_id) if client.manager_id else None)


def set_status(db: Session, client_id: int, new_status: str, actor: User) -> ClientOut:
    with conflict_guard(db):
        client = get_or_404(db, client_id, "update")
        if client.status == new_status:
            raise AppError(409, "invalid_transition", f"Client is already {new_status.lower()}.")
        if new_status == INACTIVE:
            deps = supervisors_on_client(db, client.id)
            if deps:
                raise AppError(409, "has_dependent_assignments",
                               "Move these Supervisors to another client (or clear their client) before deactivating.",
                               {"supervisors": deps})
        client.status = new_status
        audit_service.record(db, "client.status_change", actor.id, "client", client.id, {"to": new_status})
        db.commit()
    return to_out(client, db.get(User, client.manager_id) if client.manager_id else None)


def assign_manager(db: Session, client_id: int, manager_id: int | None, reassign: bool, actor: User) -> ClientOut:
    with conflict_guard(db):
        client = get_or_404(db, client_id, "update")  # serialises concurrent changes to this client
        old_id = client.manager_id
        if manager_id is None:
            if old_id is None:
                return to_out(client, None)
            deps = supervisors_on_client(db, client.id)
            if deps:
                raise AppError(409, "has_dependent_assignments",
                               "Move these Supervisors to another client before removing the Manager.", {"supervisors": deps})
            client.manager_id = None
            event, meta = "client_manager_removed", {"from": old_id, "to": None}
            hist_manager = old_id
        else:
            manager = db.scalar(select(User).where(User.id == manager_id).with_for_update(read=True))
            if manager is None:
                raise AppError(404, "manager_not_found", "Manager not found.")
            if manager.role != MANAGER:
                raise AppError(422, "invalid_manager", "The selected user is not a Manager.")
            if manager.status != ACTIVE:
                raise AppError(409, "manager_inactive", "The selected Manager is not active.")
            if client.status != ACTIVE:
                raise AppError(409, "client_inactive", "Inactive clients cannot be assigned to a Manager.")
            if old_id == manager_id:
                return to_out(client, manager)
            if old_id is not None:
                current = db.get(User, old_id)
                if not reassign:
                    raise AppError(409, "client_has_manager",
                                   "This client already has a Manager. Use the reassignment workflow to change it.",
                                   {"current_manager": brief(current)})
                deps = supervisors_on_client(db, client.id)
                if deps:
                    raise AppError(409, "has_dependent_assignments",
                                   "Move these Supervisors to another client before reassigning this client's Manager.",
                                   {"supervisors": deps})
            client.manager_id = manager_id
            event = "client_manager_reassigned" if old_id else "client_manager_assigned"
            meta, hist_manager = {"from": old_id, "to": manager_id}, manager_id
        db.flush()
        db.add(AssignmentHistory(event_type=event, manager_id=hist_manager, client_id=client.id, actor_user_id=actor.id))
        audit_service.record(db, "client." + event.removeprefix("client_"), actor.id, "client", client.id, meta)
        db.commit()
        return to_out(client, db.get(User, client.manager_id) if client.manager_id else None)
