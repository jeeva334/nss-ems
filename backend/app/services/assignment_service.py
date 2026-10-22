from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.constants import ACTIVE, INACTIVE, MANAGER, SUPERVISOR
from app.core.errors import AppError
from app.models import AssignmentHistory, Client, SupervisorAssignment, User
from app.services import audit_service
from app.services.client_service import brief
from app.services.db_guard import conflict_guard


def _supervisor(db: Session, user_id: int) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise AppError(404, "user_not_found", "User not found.")
    if u.role != SUPERVISOR:
        raise AppError(409, "not_a_supervisor", "This action applies to Supervisors only.")
    return u


def _lock_assignment(db: Session, supervisor_id: int) -> SupervisorAssignment | None:
    # FOR NO KEY UPDATE does not conflict with the FK checks other transactions run on this row (no deadlocks).
    return db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == supervisor_id)
                     .with_for_update(key_share=True))


def _history(db, event, sup_id=None, mgr_id=None, client_id=None, actor_id=None):
    db.add(AssignmentHistory(event_type=event, supervisor_id=sup_id, manager_id=mgr_id,
                             client_id=client_id, actor_user_id=actor_id))


def remove_mapping_no_commit(db: Session, sup: User, actor_id: int, event: str = "supervisor_unmapped") -> bool:
    a = _lock_assignment(db, sup.id)
    if a is None:
        return False
    _history(db, event, sup.id, a.manager_id, a.client_id, actor_id)
    audit_service.record(db, "supervisor." + event.removeprefix("supervisor_"), actor_id, "user", sup.id,
                         {"manager": a.manager_id, "client": a.client_id})
    db.delete(a)
    db.flush()
    return True


def map_manager(db: Session, supervisor_id: int, manager_id: int | None, clear_client: bool, actor: User) -> dict:
    with conflict_guard(db):
        sup = _supervisor(db, supervisor_id)
        if manager_id is None:
            remove_mapping_no_commit(db, sup, actor.id)
            db.commit()
            return {"manager": None, "client": None}
        if sup.status == INACTIVE:
            raise AppError(409, "user_inactive", "Inactive Supervisors cannot be assigned.")
        manager = db.scalar(select(User).where(User.id == manager_id).with_for_update(read=True))
        if manager is None:
            raise AppError(404, "manager_not_found", "Manager not found.")
        if manager.role != MANAGER:
            raise AppError(422, "invalid_manager", "The selected user is not a Manager.")
        if manager.status != ACTIVE:
            raise AppError(409, "manager_inactive", "The selected Manager is not active.")
        a = _lock_assignment(db, sup.id)
        if a is None:
            db.add(SupervisorAssignment(supervisor_id=sup.id, manager_id=manager.id, created_by_user_id=actor.id))
            _history(db, "supervisor_mapped", sup.id, manager.id, None, actor.id)
            audit_service.record(db, "supervisor.map_manager", actor.id, "user", sup.id, {"from": None, "to": manager.id})
        elif a.manager_id != manager.id:
            if a.client_id is not None:
                if not clear_client:
                    cl = db.get(Client, a.client_id)
                    raise AppError(409, "has_client_assignment",
                                   "This Supervisor is assigned to a client of the current Manager. "
                                   "Confirm clearing that client assignment to change the Manager.",
                                   {"client": {"id": cl.id, "client_code": cl.client_code, "client_name": cl.client_name}})
                _history(db, "supervisor_client_cleared", sup.id, a.manager_id, a.client_id, actor.id)
            old = a.manager_id
            a.manager_id, a.client_id = manager.id, None  # one UPDATE: never an inconsistent intermediate row
            _history(db, "supervisor_remapped", sup.id, manager.id, None, actor.id)
            audit_service.record(db, "supervisor.map_manager", actor.id, "user", sup.id, {"from": old, "to": manager.id})
        db.commit()
    return current(db, sup.id)


def assign_client(db: Session, supervisor_id: int, client_id: int | None, actor: User) -> dict:
    with conflict_guard(db):
        sup = _supervisor(db, supervisor_id)
        a = _lock_assignment(db, sup.id)
        if a is None:
            raise AppError(409, "no_manager_mapping", "Map this Supervisor to a Manager before assigning a client.")
        if client_id is None:
            if a.client_id is not None:
                _history(db, "supervisor_client_cleared", sup.id, a.manager_id, a.client_id, actor.id)
                audit_service.record(db, "supervisor.clear_client", actor.id, "user", sup.id, {"client": a.client_id})
                a.client_id = None
            db.commit()
            return current(db, sup.id)
        if sup.status == INACTIVE:
            raise AppError(409, "user_inactive", "Inactive Supervisors cannot be assigned.")
        client = db.scalar(select(Client).where(Client.id == client_id).with_for_update(read=True))
        if client is None:
            raise AppError(404, "client_not_found", "Client not found.")
        if client.status != ACTIVE:
            raise AppError(409, "client_inactive", "Inactive clients cannot be assigned.")
        if client.manager_id != a.manager_id:  # the backend validates even though the UI filters options
            raise AppError(409, "client_not_under_manager", "This client does not belong to the Supervisor's Manager.")
        if a.client_id != client.id:
            event = "supervisor_client_changed" if a.client_id else "supervisor_client_assigned"
            audit_service.record(db, "supervisor." + event.removeprefix("supervisor_"), actor.id, "user", sup.id,
                                 {"from": a.client_id, "to": client.id})
            a.client_id = client.id
            _history(db, event, sup.id, a.manager_id, client.id, actor.id)
        db.commit()
    return current(db, sup.id)


def current(db: Session, supervisor_id: int) -> dict:
    a = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == supervisor_id))
    if a is None:
        return {"manager": None, "client": None}
    cl = db.get(Client, a.client_id) if a.client_id else None
    return {"manager": brief(db.get(User, a.manager_id)),
            "client": {"id": cl.id, "client_code": cl.client_code, "client_name": cl.client_name} if cl else None}


def history_for(db: Session, user: User, limit: int = 50) -> list[dict]:
    sup, mgr, act = aliased(User), aliased(User), aliased(User)
    stmt = (select(AssignmentHistory, sup.full_name, mgr.full_name, Client.client_code, act.full_name)
            .outerjoin(sup, sup.id == AssignmentHistory.supervisor_id)
            .outerjoin(mgr, mgr.id == AssignmentHistory.manager_id)
            .outerjoin(Client, Client.id == AssignmentHistory.client_id)
            .outerjoin(act, act.id == AssignmentHistory.actor_user_id))
    if user.role == SUPERVISOR:
        stmt = stmt.where(AssignmentHistory.supervisor_id == user.id)
    elif user.role == MANAGER:
        stmt = stmt.where(AssignmentHistory.manager_id == user.id)
    else:
        return []
    rows = db.execute(stmt.order_by(AssignmentHistory.id.desc()).limit(limit)).all()
    return [{"id": h.id, "event_type": h.event_type, "supervisor": s, "manager": m, "client_code": cc,
             "actor": a, "created_at": h.created_at} for h, s, m, cc, a in rows]
