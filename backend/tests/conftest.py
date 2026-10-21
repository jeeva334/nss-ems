import os
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://manpower:devpassword@localhost:5432/manpower_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import User

PASSWORD = "CorrectHorse42Battery"
TABLES = "assignment_history, supervisor_assignments, invitations, sessions, audit_logs, clients, users"


@pytest.fixture(scope="session", autouse=True)
def migrated():
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")  # tests exercise the real migration


@pytest.fixture(autouse=True)
def clean():
    limiter.reset()
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        c.execute(text("ALTER SEQUENCE employee_id_seq RESTART WITH 1"))  # test isolation only


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user(db):
    n = {"i": 0}

    def _make(role="ADMIN", status="ACTIVE", password=PASSWORD, email=None):
        n["i"] += 1
        u = User(full_name=f"User {n['i']}", email=email or f"user{n['i']}@example.com",
                 mobile_number="9876543210", role=role, status=status,
                 password_hash=hash_password(password) if password else None)
        db.add(u)
        db.commit()
        return u
    return _make


class FakeSender:
    provider = "fake"

    def __init__(self):
        self.sent, self.fail_with = [], None

    def send(self, to, subject, body_html):
        from app.services.email_service import EmailDeliveryError
        if self.fail_with:
            raise EmailDeliveryError(self.fail_with)
        self.sent.append((to, body_html))

    def last_token(self):
        import re
        return re.search(r"#token=([\w\-]+)", self.sent[-1][1]).group(1)


@pytest.fixture
def sender(monkeypatch):
    fake = FakeSender()
    monkeypatch.setattr("app.services.email_service.get_email_sender", lambda: fake)
    return fake


@pytest.fixture
def admin_client(client, make_user):
    """Logged-in Admin TestClient that sends the CSRF header automatically."""
    admin = make_user("ADMIN")
    r = client.post("/api/v1/auth/login", json={"identifier": admin.email, "password": PASSWORD})
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    client.admin = admin
    return client


def new_user_payload(**over):
    p = {"full_name": "Asha Rao", "mobile_number": "+91 98765-43210", "email": "Asha@Example.com", "role": "SUPERVISOR"}
    p.update(over)
    return p
