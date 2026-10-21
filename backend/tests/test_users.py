import threading

import pytest
from sqlalchemy import select, text

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models import AuditLog, Client, Invitation, SupervisorAssignment, User
from app.services import invitation_service
from tests.conftest import PASSWORD, new_user_payload

U = "/api/v1/users"


def create(c, **over):
    return c.post(U, json=new_user_payload(**over))


# ---------- authorization ----------
def test_user_endpoints_require_admin(client, make_user, admin_client):
    admin_client.post("/api/v1/auth/logout")
    for role in ("MANAGER", "SUPERVISOR"):
        u = make_user(role)
        r = client.post("/api/v1/auth/login", json={"identifier": u.email, "password": PASSWORD})
        client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
        assert client.get(U).status_code == 403
        assert create(client).status_code == 403
        assert client.patch(f"{U}/1/status", json={"status": "INACTIVE"}).status_code == 403
        client.post("/api/v1/auth/logout")


def test_unauthenticated_and_csrf(client, admin_client):
    assert create(client.__class__(client.app)).status_code == 401
    del admin_client.headers["X-CSRF-Token"]
    assert create(admin_client).status_code == 403


# ---------- creation ----------
def test_create_user_generates_employee_id_and_invites(admin_client, sender, db):
    r = create(admin_client)
    assert r.status_code == 201
    b = r.json()
    assert b["user"]["employee_id"] == "EMP0002"  # EMP0001 is the logged-in admin
    assert b["user"]["status"] == "PENDING" and b["user"]["email"] == "asha@example.com"
    assert b["user"]["mobile_number"] == "+919876543210"
    assert b["delivery"] == {"status": "sent", "provider": "fake", "error": None}
    assert sender.sent[0][0] == "asha@example.com"
    inv = db.scalar(select(Invitation))
    assert inv.token_hash != sender.last_token() and len(inv.token_hash) == 64
    assert db.scalar(select(User).where(User.email == "asha@example.com")).password_hash is None


def test_employee_id_cannot_be_supplied(admin_client, sender):
    r = create(admin_client, employee_id="EMP9999")
    assert r.json()["user"]["employee_id"] != "EMP9999"


def test_duplicate_email_case_insensitive(admin_client, sender):
    assert create(admin_client).status_code == 201
    r = create(admin_client, email="ASHA@example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_email"


@pytest.mark.parametrize("over,field", [({"role": "OWNER"}, "role"), ({"mobile_number": "abc"}, "mobile_number"),
                                        ({"email": "nope"}, "email"), ({"full_name": " "}, "full_name")])
def test_validation_errors_name_the_field(admin_client, sender, over, field):
    r = create(admin_client, **over)
    assert r.status_code == 422
    assert any(field in f["field"] for f in r.json()["error"]["details"]["fields"])


def test_email_failure_preserves_account_and_allows_resend(admin_client, sender, db):
    sender.fail_with = "provider_http_503"
    r = create(admin_client)
    assert r.status_code == 201 and r.json()["delivery"]["status"] == "failed"
    uid = r.json()["user"]["id"]
    assert r.json()["user"]["status"] == "PENDING" and r.json()["invitation"]["state"] == "SEND_FAILED"
    assert admin_client.get(f"{U}/{uid}").json()["invitation"]["send_error"] == "provider_http_503"
    assert create(admin_client).status_code == 409  # retry cannot duplicate the account
    sender.fail_with = None
    r2 = admin_client.post(f"{U}/{uid}/invitations")
    assert r2.status_code == 201 and r2.json()["delivery"]["status"] == "sent"
    assert db.scalar(select(Invitation).where(Invitation.revoked_at.is_(None), Invitation.sent_at.is_not(None)))


# ---------- activation ----------
def activate(client, token, pw="NewPassword12345", confirm=None):
    return client.post("/api/v1/auth/activate", json={"token": token, "password": pw, "confirm_password": confirm or pw})


def test_full_activation_flow_and_login(admin_client, sender, client):
    from fastapi.testclient import TestClient
    create(admin_client)
    fresh = TestClient(client.app)
    assert fresh.post("/api/v1/auth/login", json={"identifier": "asha@example.com", "password": "NewPassword12345"}).status_code == 401
    assert activate(fresh, sender.last_token()).status_code == 200
    r = fresh.post("/api/v1/auth/login", json={"identifier": "EMP0002", "password": "NewPassword12345"})
    assert r.status_code == 200 and r.json()["user"]["status"] == "ACTIVE"


def test_token_single_use(admin_client, sender, client):
    create(admin_client)
    t = sender.last_token()
    assert activate(client, t).status_code == 200
    r = activate(client, t, "AnotherPassword123")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invitation_invalid"


def test_expired_token(admin_client, sender, client, db):
    create(admin_client)
    db.execute(text("UPDATE invitations SET expires_at = now() - interval '1 minute'"))
    db.commit()
    r = activate(client, sender.last_token())
    assert r.status_code == 400 and r.json()["error"]["code"] == "invitation_expired"


def test_resend_revokes_older_token(admin_client, sender, client):
    uid = create(admin_client).json()["user"]["id"]
    old = sender.last_token()
    admin_client.post(f"{U}/{uid}/invitations")
    new = sender.last_token()
    assert old != new
    assert activate(client, old).json()["error"]["code"] == "invitation_invalid"
    assert activate(client, new).status_code == 200


def test_revoke_invitation(admin_client, sender, client):
    uid = create(admin_client).json()["user"]["id"]
    assert admin_client.post(f"{U}/{uid}/invitations/revoke").status_code == 204
    assert activate(client, sender.last_token()).status_code == 400
    assert admin_client.post(f"{U}/{uid}/invitations/revoke").status_code == 409
    assert admin_client.get(f"{U}/{uid}").json()["invitation"]["state"] == "REVOKED"


def test_inactive_account_cannot_activate_via_old_invitation(admin_client, sender, client):
    uid = create(admin_client).json()["user"]["id"]
    assert admin_client.patch(f"{U}/{uid}/status", json={"status": "INACTIVE"}).status_code == 200
    assert activate(client, sender.last_token()).status_code == 400
    # reactivating a never-activated account returns it to PENDING (needs a new invitation)
    assert admin_client.patch(f"{U}/{uid}/status", json={"status": "ACTIVE"}).json()["status"] == "PENDING"


def test_password_validation(admin_client, sender, client):
    create(admin_client)
    t = sender.last_token()
    assert activate(client, t, "short1").json()["error"]["code"] == "weak_password"
    assert activate(client, t, "NewPassword12345", "Different12345678").status_code == 422
    assert activate(client, t).status_code == 200  # token was not burned by failed attempts


def test_activation_attempts_rate_limited(client):
    for _ in range(10):
        assert activate(client, "x" * 30).status_code == 400
    assert activate(client, "x" * 30).status_code == 429


def test_concurrent_redemption_only_one_wins(admin_client, sender):
    create(admin_client)
    token, results = sender.last_token(), []

    def work():
        with SessionLocal() as s:
            try:
                invitation_service.activate(s, token, "NewPassword12345", "t")
                results.append("ok")
            except AppError as e:
                s.rollback()
                results.append(e.code)
    ts = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results.count("ok") == 1 and len(results) == 6


def test_resend_rate_limited(admin_client, sender):
    uid = create(admin_client).json()["user"]["id"]
    codes = [admin_client.post(f"{U}/{uid}/invitations").status_code for _ in range(5)]
    assert codes[:4] == [201] * 4 and codes[4] == 429


def test_cannot_invite_active_user(admin_client, make_user, sender):
    u = make_user("MANAGER")
    assert admin_client.post(f"{U}/{u.id}/invitations").status_code == 409


# ---------- list / detail ----------
@pytest.fixture
def populated(admin_client, make_user):
    make_user("MANAGER", email="mgr@example.com")
    make_user("SUPERVISOR", email="sup@example.com", status="INACTIVE")
    for i in range(25):
        make_user("SUPERVISOR", email=f"worker{i}@example.com")


def test_pagination(admin_client, populated):
    r = admin_client.get(U, params={"page_size": 10}).json()
    assert r["total"] == 28 and len(r["items"]) == 10 and r["page"] == 1
    assert len(admin_client.get(U, params={"page_size": 10, "page": 3}).json()["items"]) == 8
    ids = [u["id"] for u in admin_client.get(U, params={"page_size": 100}).json()["items"]]
    assert ids == sorted(ids, reverse=True)
    assert admin_client.get(U, params={"page_size": 101}).status_code == 422
    assert admin_client.get(U, params={"page": 0}).status_code == 422


def test_filters_and_search(admin_client, populated):
    g = lambda **p: admin_client.get(U, params=p).json()
    assert g(role="MANAGER")["total"] == 1
    assert g(status="INACTIVE")["total"] == 1
    assert g(role="ADMIN", status="ACTIVE")["total"] == 1
    assert g(q="mgr@")["total"] == 1
    assert g(q="EMP0002")["items"][0]["email"] == "mgr@example.com"
    assert g(q="9876543210")["total"] == 28
    assert g(q="User 3")["total"] >= 1
    assert g(q="%")["total"] == 0 and g(q="_")["total"] == 0  # LIKE wildcards are escaped
    assert admin_client.get(U, params={"role": "BOSS"}).status_code == 422


def test_detail_role_specific_assignments(admin_client, make_user, db):
    mgr, sup, adm = make_user("MANAGER"), make_user("SUPERVISOR"), make_user("ADMIN")
    cl = Client(client_code="C1", client_name="Acme", manager_id=mgr.id)
    db.add(cl)
    db.commit()
    db.add(SupervisorAssignment(supervisor_id=sup.id, manager_id=mgr.id, client_id=cl.id))
    db.commit()
    m = admin_client.get(f"{U}/{mgr.id}").json()["assignments"]
    assert m["clients"][0]["client_name"] == "Acme" and m["supervisors"][0]["id"] == sup.id
    s = admin_client.get(f"{U}/{sup.id}").json()["assignments"]
    assert s["manager"]["id"] == mgr.id and s["client"]["client_code"] == "C1"
    assert admin_client.get(f"{U}/{adm.id}").json()["assignments"] == {}
    assert admin_client.get(f"{U}/99999").status_code == 404


# ---------- update / status ----------
def test_update_user(admin_client, make_user):
    a, b = make_user("MANAGER"), make_user("MANAGER")
    r = admin_client.patch(f"{U}/{a.id}", json={"full_name": "New Name", "mobile_number": "9123456780"})
    assert r.status_code == 200 and r.json()["full_name"] == "New Name"
    assert r.json()["employee_id"] == a.employee_id and r.json()["role"] == "MANAGER"
    assert admin_client.patch(f"{U}/{a.id}", json={"email": b.email}).status_code == 409
    assert admin_client.patch(f"{U}/{a.id}", json={}).status_code == 422
    for forbidden in ({"role": "ADMIN"}, {"employee_id": "EMP9999"}, {"status": "ACTIVE"}):
        assert admin_client.patch(f"{U}/{a.id}", json=forbidden).status_code == 422
    assert admin_client.get(f"{U}/{a.id}").json()["user"]["role"] == "MANAGER"


def test_changing_pending_email_revokes_invitation(admin_client, sender, client):
    uid = create(admin_client).json()["user"]["id"]
    admin_client.patch(f"{U}/{uid}", json={"email": "other@example.com"})
    assert activate(client, sender.last_token()).status_code == 400


def test_deactivation_rules_and_session_revocation(admin_client, make_user, client):
    from fastapi.testclient import TestClient
    assert admin_client.patch(f"{U}/{admin_client.admin.id}/status", json={"status": "INACTIVE"}).json()["error"]["code"] == "cannot_deactivate_self"
    other = make_user("ADMIN")
    sess = TestClient(client.app)
    sess.post("/api/v1/auth/login", json={"identifier": other.email, "password": PASSWORD})
    assert sess.get("/api/v1/auth/me").status_code == 200
    assert admin_client.patch(f"{U}/{other.id}/status", json={"status": "INACTIVE"}).status_code == 200
    assert sess.get("/api/v1/auth/me").status_code == 401  # live session killed
    assert sess.post("/api/v1/auth/login", json={"identifier": other.email, "password": PASSWORD}).status_code == 401
    assert admin_client.patch(f"{U}/{other.id}/status", json={"status": "INACTIVE"}).json()["error"]["code"] == "invalid_transition"
    assert admin_client.patch(f"{U}/{other.id}/status", json={"status": "ACTIVE"}).json()["status"] == "ACTIVE"


def test_cannot_deactivate_last_admin(admin_client, make_user, db):
    a2 = make_user("ADMIN")
    db.execute(text("UPDATE users SET status='INACTIVE' WHERE id=:i"), {"i": admin_client.admin.id})  # simulate only a2 left
    db.commit()
    # a2 is the last active admin but the caller is inactive; use a fresh session for a2 instead
    # (the guard is exercised directly)
    from app.services import user_service
    with pytest.raises(AppError) as e:
        user_service.set_status(db, a2, "INACTIVE", admin_client.admin.__class__(id=999, role="ADMIN"))
    assert e.value.code == "last_admin"


def test_manager_with_clients_cannot_be_deactivated(admin_client, make_user, db):
    mgr = make_user("MANAGER")
    db.add(Client(client_code="C9", client_name="X", manager_id=mgr.id))
    db.commit()
    r = admin_client.patch(f"{U}/{mgr.id}/status", json={"status": "INACTIVE"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "has_dependent_assignments"


# ---------- audit ----------
def test_audit_trail_has_no_secrets(admin_client, sender, client, db):
    create(admin_client)
    token = sender.last_token()
    activate(client, token)
    logs = db.scalars(select(AuditLog)).all()
    actions = {l.action for l in logs}
    assert {"user.create", "invitation.issue", "invitation.sent", "auth.activate"} <= actions
    blob = str([(l.action, l.meta) for l in logs])
    assert token not in blob and "NewPassword" not in blob
