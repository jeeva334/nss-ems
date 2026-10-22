import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.errors import AppError
from app.core.rate_limit import FailureLimiter, limiter
from app.db.session import SessionLocal
from app.main import app
from app.models import AuditLog, Invitation, User
from app.schemas.user import UserCreate
from app.services import audit_service, invitation_service, user_service
from tests.conftest import PASSWORD, new_user_payload

API = "/api/v1"
PUBLIC = {("GET", f"{API}/health/live"), ("GET", f"{API}/health/ready"),
          ("POST", f"{API}/auth/login"), ("POST", f"{API}/auth/activate")}
# The public OpenAPI schema is the stable inventory of every registered endpoint.
ROUTES = sorted((m.upper(), path) for path, ops in app.openapi()["paths"].items() if path.startswith(API)
                for m in ops if m.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"})
PROTECTED = [(m, p) for m, p in ROUTES if (m, p) not in PUBLIC]


def concrete(path: str) -> str:
    import re
    return re.sub(r"\{[^}]+\}", "1", path)


def logged_in(app_, user):
    c = TestClient(app_)
    r = c.post(f"{API}/auth/login", json={"identifier": user.email, "password": PASSWORD})
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return c


# ------------------------------------------------------------------ authorization sweep over EVERY route
def test_route_inventory_is_not_empty():
    assert len(PROTECTED) >= 19, PROTECTED  # guards against the sweep silently testing nothing


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_protected_route_rejects_anonymous(method, path):
    r = TestClient(app).request(method, concrete(path))
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


LOGOUT = ("POST", f"{API}/auth/logout")
ANY_AUTH_OK = {("GET", f"{API}/auth/me")}
SPECIAL = {  # (method, path) -> {role: allowed status codes}
    ("GET", f"{API}/clients"): {"MANAGER": {200}, "SUPERVISOR": {403}},
    ("GET", f"{API}/clients/{{client_id}}"): {"MANAGER": {403, 404}, "SUPERVISOR": {403, 404}},
}


@pytest.mark.parametrize("role", ["MANAGER", "SUPERVISOR"])
def test_every_admin_route_forbidden_for_non_admins(make_user, role):
    c = logged_in(app, make_user(role))
    for method, path in PROTECTED:
        if (method, path) == LOGOUT:
            continue
        r = c.request(method, concrete(path))
        if (method, path) in ANY_AUTH_OK:
            assert r.status_code == 200
        elif (method, path) in SPECIAL:
            assert r.status_code in SPECIAL[(method, path)][role], f"{method} {path} -> {r.status_code}"
        else:
            assert r.status_code == 403, f"{role}: {method} {path} -> {r.status_code}"


def test_logout_route_requires_csrf_for_everyone(make_user):
    c = logged_in(app, make_user("MANAGER"))
    del c.headers["X-CSRF-Token"]
    assert c.post(f"{API}/auth/logout").status_code == 403


def test_state_changing_routes_all_enforce_csrf(admin_client):
    del admin_client.headers["X-CSRF-Token"]
    for method, path in PROTECTED:
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            r = admin_client.request(method, concrete(path), json={})
            assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed", f"{method} {path}"


# ------------------------------------------------------------------ transport / request hardening
def test_security_headers_present(client):
    h = client.get(f"{API}/health/live").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and h["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert "strict-transport-security" not in h  # only in production


def test_hsts_in_production(client, monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "settings", m.settings.model_copy(update={"app_env": "production"}))
    assert "max-age=31536000" in client.get(f"{API}/health/live").headers["strict-transport-security"]


def test_origin_check_on_state_changing_requests(client):
    body = {"identifier": "x@example.com", "password": "whatever"}
    bad = client.post(f"{API}/auth/login", json=body, headers={"Origin": "https://evil.example"})
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "origin_not_allowed"
    ok = client.post(f"{API}/auth/login", json=body, headers={"Origin": "http://localhost:5173"})
    assert ok.status_code == 401  # got past the origin check, failed on credentials
    assert client.get(f"{API}/health/live", headers={"Origin": "https://evil.example"}).status_code == 200


def test_oversized_body_rejected(client):
    r = client.post(f"{API}/auth/login", content=b"x" * 70_000, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_request_id_is_sanitised(client):
    assert client.get(f"{API}/health/live", headers={"X-Request-ID": "valid-id-12345"}).headers["x-request-id"] == "valid-id-12345"
    for bad in ["short", "has spaces and \t tabs here", "x" * 200, "inject<script>12345"]:
        rid = client.get(f"{API}/health/live", headers={"X-Request-ID": bad}).headers["x-request-id"]
        assert rid != bad and len(rid) == 32


def test_validation_errors_never_echo_secrets(client):
    secret = "SuperSecretValue-" + "x" * 130  # too long -> 422
    r = client.post(f"{API}/auth/login", json={"identifier": "a@b.com", "password": secret})
    assert r.status_code == 422 and secret not in r.text and "SuperSecret" not in r.text
    r = client.post(f"{API}/auth/activate", json={"token": "t" * 30, "password": "PasswordA1234567", "confirm_password": "PasswordB1234567"})
    assert r.status_code == 422 and "PasswordA" not in r.text and "PasswordB" not in r.text


def test_session_cookie_flags_in_production_config(client, make_user, monkeypatch):
    import app.api.v1.endpoints.auth as auth_ep
    prod = auth_ep.get_settings().model_copy(update={"app_env": "production", "cookie_samesite": "none"})
    monkeypatch.setattr(auth_ep, "get_settings", lambda: prod)
    u = make_user()
    cookie = client.post(f"{API}/auth/login", json={"identifier": u.email, "password": PASSWORD}).headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=none" in cookie


def test_sql_injection_attempts_are_inert(admin_client):
    for q in ["'; DROP TABLE users; --", "' OR '1'='1", "\\", "%_%", "Robert'); DELETE FROM users;--"]:
        assert admin_client.get(f"{API}/users", params={"q": q}).status_code == 200
        assert admin_client.get(f"{API}/clients", params={"q": q}).status_code == 200
        assert admin_client.get(f"{API}/audit-logs", params={"action": q}).status_code == 200
    assert admin_client.get(f"{API}/users").json()["total"] == 1


def test_password_hashes_never_in_responses(admin_client, make_user):
    make_user("MANAGER")
    for path in (f"{API}/users", f"{API}/users/1", f"{API}/auth/me", f"{API}/audit-logs"):
        body = admin_client.get(path).text
        assert "password" not in body.lower() and "$argon2" not in body


# ------------------------------------------------------------------ error handling
def test_database_outage_returns_clean_503(client):
    from app.db.session import get_db as real_get_db

    def broken():
        raise OperationalError("SELECT 1", {}, Exception("connection to server at secret-host.internal failed"))
        yield  # pragma: no cover
    app.dependency_overrides[real_get_db] = broken
    try:
        r = client.get(f"{API}/auth/me", cookies={"mp_session": "x" * 30})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json()["error"]["code"] == "service_unavailable"
    assert "secret-host" not in r.text and r.json()["error"]["correlation_id"] == r.headers["x-request-id"]


def test_unhandled_error_is_generic_with_correlation_id():
    async def boom():
        raise RuntimeError("boom-internal-detail postgres://user:pw@host")
    app.add_api_route(f"{API}/_boom", boom, methods=["GET"])
    try:
        r = TestClient(app, raise_server_exceptions=False).get(f"{API}/_boom")
    finally:
        app.router.routes = [x for x in app.router.routes if getattr(x, "path", "") != f"{API}/_boom"]
    assert r.status_code == 500 and "boom" not in r.text and "postgres://" not in r.text
    assert r.json()["error"]["correlation_id"] == r.headers["x-request-id"]
    assert r.headers["x-content-type-options"] == "nosniff"


# ------------------------------------------------------------------ shared (database-backed) rate limiter
def test_rate_limiter_state_is_shared_between_instances():
    a, b = FailureLimiter(), FailureLimiter()  # stand-ins for two worker processes
    for _ in range(3):
        a.hit("k", 60)
    with pytest.raises(AppError) as e:
        b.check("k", 3, 60)
    assert e.value.status_code == 429
    b.check("k", 4, 60)
    a.clear("k")
    b.check("k", 1, 60)


def test_rate_limiter_window_expiry_and_hashed_keys(db):
    limiter.hit("login:id:victim@example.com", 60)
    keys = [r[0] for r in db.execute(text("SELECT key_hash FROM rate_limit_events"))]
    assert keys and all("victim" not in k and len(k) == 64 for k in keys)
    db.execute(text("UPDATE rate_limit_events SET created_at = now() - interval '2 hours'"))
    db.commit()
    limiter.check("login:id:victim@example.com", 1, 60)  # old hits no longer count


def test_failures_recorded_even_though_login_returns_error(client, make_user, db):
    u = make_user()
    for _ in range(5):
        client.post(f"{API}/auth/login", json={"identifier": u.email, "password": "WrongPassword123"})
    assert db.scalar(text("SELECT count(*) FROM rate_limit_events")) >= 5


# ------------------------------------------------------------------ audit trail
def test_scrubber_redacts_secrets_and_truncates():
    out = audit_service.scrub({"password": "p", "invitation_token": "t", "nested": {"api_key": "k", "ok": 1},
                               "csrf_token": "c", "note": "x" * 1000, "role": "ADMIN", "session_id": "s"})
    assert out["password"] == out["invitation_token"] == out["csrf_token"] == out["session_id"] == "[redacted]"
    assert out["nested"] == {"api_key": "[redacted]", "ok": 1} and len(out["note"]) == 300 and out["role"] == "ADMIN"


def test_audit_record_never_persists_secrets(db):
    audit_service.record(db, "test.event", None, "user", 1, {"password": "hunter2", "token": "abc", "fine": "yes"})
    db.commit()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "test.event"))
    assert log.meta == {"password": "[redacted]", "token": "[redacted]", "fine": "yes"}


def test_audit_endpoint_admin_only(client, make_user, admin_client):
    for role in ("MANAGER", "SUPERVISOR"):
        assert logged_in(app, make_user(role)).get(f"{API}/audit-logs").status_code == 403
    assert TestClient(app).get(f"{API}/audit-logs").status_code == 401


def test_audit_trail_records_correlation_id_and_filters(admin_client, sender):
    r = admin_client.post(f"{API}/users", json=new_user_payload(), headers={"X-Request-ID": "trace-abc-12345"})
    uid = r.json()["user"]["id"]
    g = lambda **p: admin_client.get(f"{API}/audit-logs", params=p).json()
    created = [i for i in g(action="user.create")["items"]]
    assert len(created) == 1 and created[0]["correlation_id"] == "trace-abc-12345"
    assert created[0]["actor"]["employee_id"] == "EMP0001" and created[0]["target_id"] == str(uid)
    assert {i["action"] for i in g(action="invitation.")["items"]} == {"invitation.issue", "invitation.sent"}
    assert g(target_type="user", target_id=str(uid))["total"] >= 3
    assert g(actor_user_id=admin_client.admin.id)["total"] >= 4
    assert g(action="nope.")["total"] == 0
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert g(date_from=future)["total"] == 0
    assert g(date_to=future)["total"] == g()["total"]
    assert g(page_size=2)["items"].__len__() == 2 and admin_client.get(f"{API}/audit-logs", params={"page_size": 101}).status_code == 422


def test_full_flow_audit_contains_no_secrets(admin_client, sender, client):
    admin_client.post(f"{API}/users", json=new_user_payload())
    token = sender.last_token()
    client.post(f"{API}/auth/activate", json={"token": token, "password": "ActivatedPass123", "confirm_password": "ActivatedPass123"})
    blob = admin_client.get(f"{API}/audit-logs", params={"page_size": 100}).text
    assert token not in blob and "ActivatedPass" not in blob and PASSWORD not in blob and "$argon2" not in blob


# ------------------------------------------------------------------ extra concurrency
def _threads(fn, n):
    out = []
    ts = [threading.Thread(target=lambda i=i: out.append(fn(i))) for i in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return out


def test_concurrent_creation_with_same_email_has_one_winner(admin_client, sender):
    def work(i):
        with SessionLocal() as s:
            actor = s.scalar(select(User).where(User.role == "ADMIN"))
            try:
                user_service.create_user(s, UserCreate(**new_user_payload()), actor)
                return 201
            except AppError as e:
                return e.status_code
    res = _threads(work, 8)
    assert sorted(res) == [201] + [409] * 7
    with SessionLocal() as s:
        assert len(s.scalars(select(User).where(User.email == "asha@example.com")).all()) == 1


def test_concurrent_resend_leaves_exactly_one_live_invitation(admin_client, sender, db):
    uid = admin_client.post(f"{API}/users", json=new_user_payload()).json()["user"]["id"]

    def work(i):
        with SessionLocal() as s:
            try:
                invitation_service.issue_and_send(s, s.get(User, uid), 1)
                return 201
            except AppError as e:
                return e.status_code
    res = _threads(work, 5)
    assert set(res) <= {201, 409, 429} and 201 in res, res
    live = db.scalars(select(Invitation).where(Invitation.user_id == uid, Invitation.revoked_at.is_(None),
                                               Invitation.consumed_at.is_(None))).all()
    assert len(live) == 1


# ------------------------------------------------------------------ housekeeping script
def test_purge_script_removes_only_stale_rows(admin_client, db):
    db.execute(text("INSERT INTO sessions (id, user_id, csrf_token, expires_at, revoked_at) "
                    "SELECT 'old' || g, 1, 'c', now() - interval '30 days', now() - interval '30 days' FROM generate_series(1,3) g"))
    db.execute(text("INSERT INTO rate_limit_events (key_hash, created_at) VALUES ('a', now() - interval '3 days'), ('b', now())"))
    db.commit()
    before = db.scalar(text("SELECT count(*) FROM sessions"))
    out = subprocess.run([sys.executable, "-m", "scripts.purge_expired"], cwd=Path(__file__).resolve().parent.parent,
                         capture_output=True, text=True)
    assert out.returncode == 0 and "purged sessions=3 rate_limit_events=1" in out.stdout, out.stderr
    assert db.scalar(text("SELECT count(*) FROM sessions")) == before - 3  # the live admin session survives
