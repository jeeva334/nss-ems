from sqlalchemy import select, text

from app.models import AuditLog, UserSession
from app.services import auth_service
from tests.conftest import PASSWORD


def login(client, ident, pw=PASSWORD):
    return client.post("/api/v1/auth/login", json={"identifier": ident, "password": pw})


def test_login_by_email_and_employee_id(client, make_user):
    u = make_user()
    r = login(client, u.email.upper())
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["employee_id"] == "EMP0001" and "password" not in str(body).lower()
    assert "password_hash" not in body["user"]
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert login(client, "emp0001").status_code == 200


def test_me_requires_auth_and_returns_csrf(client, make_user):
    assert client.get("/api/v1/auth/me").status_code == 401
    u = make_user()
    login(client, u.email)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.json()["csrf_token"]


def test_generic_errors_do_not_reveal_account_state(client, make_user):
    make_user(email="active@example.com")
    make_user(email="pending@example.com", status="PENDING", password=None)
    make_user(email="inactive@example.com", status="INACTIVE")
    bodies = [login(client, i, pw).json() for i, pw in [
        ("active@example.com", "WrongPassword123"), ("nobody@example.com", "WrongPassword123"),
        ("pending@example.com", PASSWORD), ("inactive@example.com", PASSWORD)]]
    assert all(b == bodies[0] for b in bodies)
    assert bodies[0]["error"]["code"] == "invalid_credentials"


def test_logout_requires_csrf_then_invalidates_session(client, make_user):
    u = make_user()
    csrf = login(client, u.email).json()["csrf_token"]
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "bad"}).status_code == 403
    stolen = client.cookies.get("mp_session")
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    client.cookies.set("mp_session", stolen)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_relogin_rotates_session(client, make_user, db):
    u = make_user()
    login(client, u.email)
    first = client.cookies.get("mp_session")
    login(client, u.email)
    assert client.cookies.get("mp_session") != first
    client.cookies.set("mp_session", first)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_deactivation_revokes_sessions(client, make_user, db):
    u = make_user()
    login(client, u.email)
    u.status = "INACTIVE"
    auth_service.revoke_user_sessions(db, u.id)
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_inactive_user_with_live_session_rejected(client, make_user, db):
    u = make_user()
    login(client, u.email)
    u.status = "INACTIVE"
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_sessions_store_only_token_hash(client, make_user, db):
    u = make_user()
    login(client, u.email)
    raw = client.cookies.get("mp_session")
    assert db.get(UserSession, raw) is None
    assert db.scalar(select(UserSession).limit(1)) is not None


def test_idle_and_absolute_expiry(client, make_user, db):
    u = make_user()
    login(client, u.email)
    db.execute(text("UPDATE sessions SET last_seen_at = now() - interval '2 hours'"))
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_rate_limit_after_repeated_failures(client, make_user):
    u = make_user()
    for _ in range(5):
        assert login(client, u.email, "WrongPassword123").status_code == 401
    assert login(client, u.email, PASSWORD).status_code == 429


def test_login_audited_without_secrets(client, make_user, db):
    u = make_user()
    login(client, u.email, "WrongPassword123")
    login(client, u.email)
    logs = db.scalars(select(AuditLog)).all()
    assert {l.action for l in logs} == {"auth.login_failed", "auth.login_success"}
    assert PASSWORD not in str([l.meta for l in logs])


def test_validation_error_format(client):
    r = client.post("/api/v1/auth/login", json={"identifier": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
