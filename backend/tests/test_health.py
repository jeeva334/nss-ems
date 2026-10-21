from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live():
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_hits_real_postgres():
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "up"}


def test_correlation_id_echoed():
    r = client.get("/api/v1/health/live", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
