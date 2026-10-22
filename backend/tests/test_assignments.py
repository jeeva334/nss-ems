import threading

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models import AssignmentHistory, AuditLog, Client, SupervisorAssignment
from app.services import assignment_service, client_service
from tests.conftest import PASSWORD

C, U = "/api/v1/clients", "/api/v1/users"


def mk_client(c, code="ACME", name="Acme Ltd", **extra):
    r = c.post(C, json={"client_code": code, "client_name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def put_mgr(c, cid, mid, reassign=False):
    return c.put(f"{C}/{cid}/manager", json={"manager_id": mid, "reassign": reassign})


def map_sup(c, sid, mid, clear=False):
    return c.put(f"{U}/{sid}/manager", json={"manager_id": mid, "clear_client": clear})


def sup_client(c, sid, cid):
    return c.put(f"{U}/{sid}/client", json={"client_id": cid})


def code(r):
    return r.json()["error"]["code"]


@pytest.fixture
def world(admin_client, make_user):
    """Two managers, two clients under manager 1, one under manager 2, two supervisors."""
    w = type("W", (), {})()
    w.c = admin_client
    w.m1, w.m2 = make_user("MANAGER"), make_user("MANAGER")
    w.s1, w.s2 = make_user("SUPERVISOR"), make_user("SUPERVISOR")
    w.a, w.b, w.x = mk_client(admin_client, "A1"), mk_client(admin_client, "B1"), mk_client(admin_client, "X1")
    assert put_mgr(admin_client, w.a["id"], w.m1.id).status_code == 200
    assert put_mgr(admin_client, w.b["id"], w.m1.id).status_code == 200
    assert put_mgr(admin_client, w.x["id"], w.m2.id).status_code == 200
    return w


# ---------------- client CRUD & authorization ----------------
def test_client_create_validation_and_uniqueness(admin_client):
    c = mk_client(admin_client, " acme-01 ", "Acme", contact_email="", contact_phone="+91 90000 00000")
    assert c["client_code"] == "ACME-01" and c["contact_email"] is None and c["status"] == "ACTIVE" and c["manager_id"] is None
    assert code(admin_client.post(C, json={"client_code": "acme-01", "client_name": "Other"})) == "duplicate_client_code"
    assert admin_client.post(C, json={"client_code": "!!", "client_name": "X"}).status_code == 422
    assert admin_client.post(C, json={"client_code": "OK1", "client_name": "X", "contact_email": "bad"}).status_code == 422


def test_client_update_and_search(admin_client):
    c = mk_client(admin_client, "Q1", "Quartz Industries")
    mk_client(admin_client, "Z9", "Zinc")
    assert admin_client.patch(f"{C}/{c['id']}", json={"address": "1 Main St", "client_name": "Quartz Inc"}).json()["address"] == "1 Main St"
    assert admin_client.patch(f"{C}/{c['id']}", json={"client_code": "NEW"}).status_code == 422  # code immutable
    assert admin_client.patch(f"{C}/{c['id']}", json={"manager_id": 1}).status_code == 422
    assert admin_client.patch(f"{C}/{c['id']}", json={}).status_code == 422
    g = lambda **p: admin_client.get(C, params=p).json()
    assert g(q="quartz")["total"] == 1 and g(q="z9")["items"][0]["client_name"] == "Zinc"
    assert g(q="%")["total"] == 0 and g(status="INACTIVE")["total"] == 0
    assert admin_client.get(C, params={"page_size": 101}).status_code == 422


def test_only_admin_can_mutate_clients(client, make_user, world):
    from fastapi.testclient import TestClient
    for role in ("MANAGER", "SUPERVISOR"):
        u = make_user(role)
        t = TestClient(client.app)
        r = t.post("/api/v1/auth/login", json={"identifier": u.email, "password": PASSWORD})
        t.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        assert t.post(C, json={"client_code": "NOPE", "client_name": "No"}).status_code == 403
        assert t.patch(f"{C}/{world.a['id']}", json={"client_name": "Hack"}).status_code == 403
        assert t.patch(f"{C}/{world.a['id']}/status", json={"status": "INACTIVE"}).status_code == 403
        assert put_mgr(t, world.a["id"], u.id).status_code == 403
        assert t.put(f"{U}/{world.s1.id}/client", json={"client_id": None}).status_code == 403
        assert t.put(f"{U}/{world.s1.id}/manager", json={"manager_id": None}).status_code == 403
    assert TestClient(client.app).get(C).status_code == 401


def test_manager_sees_only_own_clients(client, world):
    from fastapi.testclient import TestClient
    t = TestClient(client.app)
    t.post("/api/v1/auth/login", json={"identifier": world.m1.email, "password": PASSWORD})
    ids = {c["id"] for c in t.get(C, params={"page_size": 100}).json()["items"]}
    assert ids == {world.a["id"], world.b["id"]}
    # manager_id filter cannot be abused to peek at someone else's clients
    assert {c["id"] for c in t.get(C, params={"manager_id": world.m2.id}).json()["items"]} == ids
    assert t.get(f"{C}/{world.a['id']}").status_code == 200
    assert t.get(f"{C}/{world.x['id']}").status_code == 403


def test_supervisor_can_view_only_assigned_client_without_colleagues(client, world):
    from fastapi.testclient import TestClient
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    t = TestClient(client.app)
    t.post("/api/v1/auth/login", json={"identifier": world.s1.email, "password": PASSWORD})
    r = t.get(f"{C}/{world.a['id']}")
    assert r.status_code == 200 and r.json()["supervisors"] == []
    assert t.get(f"{C}/{world.b['id']}").status_code == 403
    assert t.get(C).status_code == 403


# ---------------- client <-> manager ----------------
def test_assign_validations(admin_client, make_user):
    c = mk_client(admin_client, "V1")
    sup, adm = make_user("SUPERVISOR"), make_user("ADMIN")
    inactive = make_user("MANAGER", status="INACTIVE")
    assert code(put_mgr(admin_client, c["id"], sup.id)) == "invalid_manager"
    assert code(put_mgr(admin_client, c["id"], adm.id)) == "invalid_manager"
    assert code(put_mgr(admin_client, c["id"], inactive.id)) == "manager_inactive"
    assert code(put_mgr(admin_client, c["id"], 99999)) == "manager_not_found"
    assert put_mgr(admin_client, 99999, 1).status_code == 404
    m = make_user("MANAGER")
    admin_client.patch(f"{C}/{c['id']}/status", json={"status": "INACTIVE"})
    assert code(put_mgr(admin_client, c["id"], m.id)) == "client_inactive"


def test_reassignment_requires_explicit_flag(world, make_user):
    r = put_mgr(world.c, world.a["id"], world.m2.id)
    assert r.status_code == 409 and code(r) == "client_has_manager"
    assert r.json()["error"]["details"]["current_manager"]["id"] == world.m1.id
    ok = put_mgr(world.c, world.a["id"], world.m2.id, reassign=True)
    assert ok.status_code == 200 and ok.json()["manager_id"] == world.m2.id and ok.json()["manager"]["id"] == world.m2.id
    assert put_mgr(world.c, world.a["id"], world.m2.id).status_code == 200  # idempotent


def test_reassignment_blocked_while_supervisors_depend_on_client(world, db):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    r = put_mgr(world.c, world.a["id"], world.m2.id, reassign=True)
    assert r.status_code == 409 and code(r) == "has_dependent_assignments"
    assert [s["id"] for s in r.json()["error"]["details"]["supervisors"]] == [world.s1.id]
    assert put_mgr(world.c, world.a["id"], None).status_code == 409
    # unaffected client of the same manager can still be moved
    assert put_mgr(world.c, world.b["id"], world.m2.id, reassign=True).status_code == 200
    # explicit resolution: clear the supervisor's client, then it works
    assert sup_client(world.c, world.s1.id, None).status_code == 200
    assert put_mgr(world.c, world.a["id"], world.m2.id, reassign=True).status_code == 200
    # supervisor kept their manager mapping but has no (now invalid) client
    a = db.scalar(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == world.s1.id))
    assert a.manager_id == world.m1.id and a.client_id is None


def test_remove_manager_and_history(world, db):
    r = put_mgr(world.c, world.b["id"], None)
    assert r.status_code == 200 and r.json()["manager_id"] is None
    events = [h.event_type for h in db.scalars(select(AssignmentHistory).order_by(AssignmentHistory.id))]
    assert events.count("client_manager_assigned") == 3 and events[-1] == "client_manager_removed"
    assert world.c.get(C, params={"unassigned": True}).json()["total"] == 1


def test_client_deactivation_requires_resolution(world):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    r = world.c.patch(f"{C}/{world.a['id']}/status", json={"status": "INACTIVE"})
    assert r.status_code == 409 and code(r) == "has_dependent_assignments"
    assert r.json()["error"]["details"]["supervisors"][0]["id"] == world.s1.id
    sup_client(world.c, world.s1.id, world.b["id"])  # move supervisor, then it's allowed
    assert world.c.patch(f"{C}/{world.a['id']}/status", json={"status": "INACTIVE"}).status_code == 200
    assert world.c.patch(f"{C}/{world.a['id']}/status", json={"status": "INACTIVE"}).status_code == 409


def test_cannot_deactivate_manager_with_clients(world):
    r = world.c.patch(f"{U}/{world.m1.id}/status", json={"status": "INACTIVE"})
    assert r.status_code == 409 and code(r) == "has_dependent_assignments"


# ---------------- supervisor <-> manager ----------------
def test_map_supervisor_to_manager(world, db):
    r = map_sup(world.c, world.s1.id, world.m1.id)
    assert r.status_code == 200 and r.json()["manager"]["id"] == world.m1.id and r.json()["client"] is None
    assert map_sup(world.c, world.s1.id, world.m1.id).status_code == 200  # idempotent, no duplicate row
    assert len(db.scalars(select(SupervisorAssignment)).all()) == 1
    assert code(map_sup(world.c, world.m2.id, world.m1.id)) == "not_a_supervisor"
    assert code(map_sup(world.c, world.s2.id, world.s1.id)) == "invalid_manager"
    assert map_sup(world.c, 99999, world.m1.id).status_code == 404
    assert map_sup(world.c, world.s1.id, 99999).status_code == 404


def test_remap_requires_explicit_client_clearing(world):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    r = map_sup(world.c, world.s1.id, world.m2.id)
    assert r.status_code == 409 and code(r) == "has_client_assignment"
    assert r.json()["error"]["details"]["client"]["client_code"] == "A1"
    ok = map_sup(world.c, world.s1.id, world.m2.id, clear=True)
    assert ok.status_code == 200 and ok.json() == {"manager": {**ok.json()["manager"], "id": world.m2.id}, "client": None}


def test_unmap_supervisor(world, db):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    assert map_sup(world.c, world.s1.id, None).json() == {"manager": None, "client": None}
    assert db.scalar(select(SupervisorAssignment)) is None
    assert map_sup(world.c, world.s1.id, None).status_code == 200  # nothing to unmap is fine


def test_inactive_manager_or_supervisor_cannot_be_mapped(world, make_user):
    inactive_m = make_user("MANAGER", status="INACTIVE")
    assert code(map_sup(world.c, world.s1.id, inactive_m.id)) == "manager_inactive"
    inactive_s = make_user("SUPERVISOR", status="INACTIVE")
    assert code(map_sup(world.c, inactive_s.id, world.m1.id)) == "user_inactive"


# ---------------- supervisor <-> client ----------------
def test_assign_client_requires_mapping_and_matching_manager(world):
    assert code(sup_client(world.c, world.s1.id, world.a["id"])) == "no_manager_mapping"
    map_sup(world.c, world.s1.id, world.m1.id)
    # client of ANOTHER manager is rejected by the backend regardless of what the UI offers
    r = sup_client(world.c, world.s1.id, world.x["id"])
    assert r.status_code == 409 and code(r) == "client_not_under_manager"
    unassigned = mk_client(world.c, "U1")
    assert code(sup_client(world.c, world.s1.id, unassigned["id"])) == "client_not_under_manager"
    assert sup_client(world.c, world.s1.id, 99999).status_code == 404
    r = sup_client(world.c, world.s1.id, world.a["id"])
    assert r.status_code == 200 and r.json()["client"]["client_code"] == "A1" and r.json()["manager"]["id"] == world.m1.id


def test_change_and_clear_client(world, db):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    assert sup_client(world.c, world.s1.id, world.b["id"]).json()["client"]["client_code"] == "B1"
    assert sup_client(world.c, world.s1.id, None).json()["client"] is None
    events = [h.event_type for h in db.scalars(select(AssignmentHistory)
              .where(AssignmentHistory.supervisor_id == world.s1.id).order_by(AssignmentHistory.id))]
    assert events == ["supervisor_mapped", "supervisor_client_assigned", "supervisor_client_changed", "supervisor_client_cleared"]


def test_inactive_client_rejected(world):
    map_sup(world.c, world.s1.id, world.m1.id)
    world.c.patch(f"{C}/{world.a['id']}/status", json={"status": "INACTIVE"})
    assert code(sup_client(world.c, world.s1.id, world.a["id"])) == "client_inactive"


def test_supervisor_deactivation_removes_mapping_with_history(world, db):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    assert world.c.patch(f"{U}/{world.s1.id}/status", json={"status": "INACTIVE"}).status_code == 200
    assert db.scalar(select(SupervisorAssignment)) is None
    last = db.scalars(select(AssignmentHistory).order_by(AssignmentHistory.id.desc())).first()
    assert last.event_type == "supervisor_unmapped_on_deactivation" and last.client_id == world.a["id"]
    assert world.c.get(f"{U}/{world.m1.id}").json()["assignments"]["supervisors"] == []


def test_history_and_filters_endpoints(world):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    h = world.c.get(f"{U}/{world.s1.id}/assignments").json()
    assert h["assignments"]["client"]["client_code"] == "A1"
    assert [e["event_type"] for e in h["history"]] == ["supervisor_client_assigned", "supervisor_mapped"]
    assert h["history"][0]["actor"] and h["history"][0]["client_code"] == "A1"
    assert any(e["event_type"] == "supervisor_mapped" for e in world.c.get(f"{U}/{world.m1.id}/assignments").json()["history"])
    mapped = lambda v: world.c.get(U, params={"role": "SUPERVISOR", "mapped": v}).json()["total"]
    assert mapped("true") == 1 and mapped("false") == 1


def test_audit_entries_written(world, db):
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    acts = {a.action for a in db.scalars(select(AuditLog))}
    assert {"client.create", "client.manager_assigned", "supervisor.map_manager", "supervisor.client_assigned"} <= acts


# ---------------- concurrency ----------------
def _run(fn, n):
    out = []

    def w(i):
        with SessionLocal() as s:
            out.append(fn(s, i))
    ts = [threading.Thread(target=w, args=(i,)) for i in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return out


def _admin(db):
    from app.models import User
    return db.scalar(select(User).where(User.role == "ADMIN"))


def _try(f):
    try:
        f()
        return 200
    except Exception as e:  # AppError carries status_code
        return getattr(e, "status_code", 500)


def test_concurrent_assignment_of_same_client_has_one_winner(admin_client, make_user):
    managers = [make_user("MANAGER") for _ in range(6)]
    c = mk_client(admin_client, "RACE")
    statuses = _run(lambda s, i: _try(lambda: client_service.assign_manager(s, c["id"], managers[i].id, False, _admin(s))), 6)
    assert sorted(statuses) == [200] + [409] * 5
    with SessionLocal() as s:
        assert s.get(Client, c["id"]).manager_id in {m.id for m in managers}


def test_race_between_supervisor_assignment_and_manager_reassignment_never_corrupts(admin_client, make_user):
    for attempt in range(8):
        m1, m2, sup = make_user("MANAGER"), make_user("MANAGER"), make_user("SUPERVISOR")
        c = mk_client(admin_client, f"R{attempt}")
        put_mgr(admin_client, c["id"], m1.id)
        map_sup(admin_client, sup.id, m1.id)
        ops = [lambda s: assignment_service.assign_client(s, sup.id, c["id"], _admin(s)),
               lambda s: client_service.assign_manager(s, c["id"], m2.id, True, _admin(s))]
        statuses = _run(lambda s, i: _try(lambda: ops[i](s)), 2)
        assert 500 not in statuses, statuses
        with SessionLocal() as s:
            a = s.scalar(select(SupervisorAssignment).where(SupervisorAssignment.supervisor_id == sup.id))
            cl = s.get(Client, c["id"])
            if a.client_id is not None:  # the invariant the database guarantees
                assert cl.manager_id == a.manager_id


def test_race_manager_deactivation_vs_client_assignment(admin_client, make_user):
    from app.services import user_service
    for attempt in range(6):
        m = make_user("MANAGER")
        c = mk_client(admin_client, f"D{attempt}")
        ops = [lambda s: client_service.assign_manager(s, c["id"], m.id, False, _admin(s)),
               lambda s: user_service.set_status(s, s.get(type(m), m.id), "INACTIVE", _admin(s))]
        statuses = _run(lambda s, i: _try(lambda: ops[i](s)), 2)
        assert 500 not in statuses, statuses
        with SessionLocal() as s:
            mgr, cl = s.get(type(m), m.id), s.get(Client, c["id"])
            # never an inactive manager that still owns the client
            assert not (mgr.status == "INACTIVE" and cl.manager_id == mgr.id)


def test_db_still_rejects_direct_inconsistency(world, db):
    from sqlalchemy.exc import IntegrityError
    map_sup(world.c, world.s1.id, world.m1.id)
    sup_client(world.c, world.s1.id, world.a["id"])
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE clients SET manager_id=:m WHERE id=:c"), {"m": world.m2.id, "c": world.a["id"]})
    db.rollback()
