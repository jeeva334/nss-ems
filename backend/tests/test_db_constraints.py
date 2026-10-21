import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models import Client, SupervisorAssignment, User
from app.services.bootstrap_service import create_initial_admin


def test_employee_id_sequence_format(make_user):
    assert [make_user("MANAGER").employee_id for _ in range(3)] == ["EMP0001", "EMP0002", "EMP0003"]


def test_employee_id_never_reused_after_delete(make_user, db):
    a = make_user()
    db.delete(a)
    db.commit()
    assert make_user().employee_id == "EMP0002"


def test_employee_id_immutable(make_user, db):
    u = make_user()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE users SET employee_id='EMP9999' WHERE id=:i"), {"i": u.id})
    db.rollback()


def test_concurrent_creation_yields_unique_ids(make_user):
    make_user()
    ids, errs = [], []

    def work(i):
        try:
            with SessionLocal() as s:
                u = User(full_name="C", email=f"c{i}@example.com", mobile_number="9876543210",
                         role="SUPERVISOR", status="PENDING")
                s.add(u)
                s.commit()
                ids.append(u.employee_id)
        except Exception as e:  # pragma: no cover
            errs.append(e)
    ts = [threading.Thread(target=work, args=(i,)) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs and len(set(ids)) == 20


def test_email_unique_and_lowercase(make_user, db):
    make_user(email="a@example.com")
    with pytest.raises(IntegrityError):
        make_user(email="a@example.com")
    db.rollback()
    with pytest.raises(IntegrityError):
        db.add(User(full_name="X", email="UPPER@example.com", mobile_number="1", role="ADMIN", status="PENDING"))
        db.commit()


def test_active_requires_password_and_valid_role(db):
    for kwargs in ({"role": "ADMIN", "status": "ACTIVE"}, {"role": "BOSS", "status": "PENDING"}):
        with pytest.raises(IntegrityError):
            db.add(User(full_name="X", email="x@example.com", mobile_number="1", **kwargs))
            db.commit()
        db.rollback()


def _client(db, mgr_id, code="C1"):
    c = Client(client_code=code, client_name=code, manager_id=mgr_id)
    db.add(c)
    db.commit()
    return c


def test_client_manager_must_be_manager_role(make_user, db):
    mgr, sup = make_user("MANAGER"), make_user("SUPERVISOR")
    assert _client(db, mgr.id).manager_id == mgr.id
    for bad in (sup.id, make_user("ADMIN").id):
        with pytest.raises(IntegrityError):
            _client(db, bad, "C2")
        db.rollback()


def test_supervisor_assignment_consistency(make_user, db):
    m1, m2, sup = make_user("MANAGER"), make_user("MANAGER"), make_user("SUPERVISOR")
    c1, c2 = _client(db, m1.id, "A"), _client(db, m2.id, "B")
    # client belonging to a different manager is rejected
    with pytest.raises(IntegrityError):
        db.add(SupervisorAssignment(supervisor_id=sup.id, manager_id=m1.id, client_id=c2.id))
        db.commit()
    db.rollback()
    db.add(SupervisorAssignment(supervisor_id=sup.id, manager_id=m1.id, client_id=c1.id))
    db.commit()
    # only one current assignment per supervisor
    with pytest.raises(IntegrityError):
        db.add(SupervisorAssignment(supervisor_id=sup.id, manager_id=m1.id))
        db.commit()
    db.rollback()
    # reassigning a client's manager while a supervisor depends on it is blocked, never silent
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE clients SET manager_id=:m WHERE id=:c"), {"m": m2.id, "c": c1.id})
    db.rollback()


def test_supervisor_role_enforced_on_assignment(make_user, db):
    m, notsup = make_user("MANAGER"), make_user("MANAGER")
    with pytest.raises(IntegrityError):
        db.add(SupervisorAssignment(supervisor_id=notsup.id, manager_id=m.id))
        db.commit()


def test_bootstrap_admin_once_only(db):
    u = create_initial_admin(db, "Root", "Root@Example.com", "9876543210", "StrongPassword123")
    assert u.employee_id == "EMP0001" and u.email == "root@example.com" and u.status == "ACTIVE"
    with pytest.raises(AppError) as e:
        create_initial_admin(db, "Two", "two@example.com", "9876543210", "StrongPassword123")
    assert e.value.code == "admin_exists"


def test_bootstrap_rejects_weak_password(db):
    with pytest.raises(AppError):
        create_initial_admin(db, "Root", "r@example.com", "9876543210", "short")
