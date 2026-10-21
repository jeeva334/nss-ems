import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_roles
from app.api.v1.endpoints import auth
from app.core.errors import AppError
from tests.conftest import PASSWORD


@pytest.fixture
def rbac_client():
    from app.main import app_error
    app = FastAPI()
    app.add_exception_handler(AppError, app_error)
    app.include_router(auth.router, prefix="/api/v1")

    @app.get("/admin-only")
    def admin_only(u=Depends(require_roles("ADMIN"))):
        return {"ok": True}

    @app.get("/staff")
    def staff(u=Depends(require_roles("ADMIN", "MANAGER"))):
        return {"ok": True}
    return TestClient(app)


def _login(c, u):
    assert c.post("/api/v1/auth/login", json={"identifier": u.email, "password": PASSWORD}).status_code == 200


def test_unauthenticated_gets_401(rbac_client):
    assert rbac_client.get("/admin-only").status_code == 401


@pytest.mark.parametrize("role,admin_ok,staff_ok", [
    ("ADMIN", 200, 200), ("MANAGER", 403, 200), ("SUPERVISOR", 403, 403)])
def test_role_matrix(rbac_client, make_user, role, admin_ok, staff_ok):
    _login(rbac_client, make_user(role))
    assert rbac_client.get("/admin-only").status_code == admin_ok
    assert rbac_client.get("/staff").status_code == staff_ok
