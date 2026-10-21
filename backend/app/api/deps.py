import hmac
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import forbidden, unauthenticated, AppError
from app.db.session import get_db
from app.models import User, UserSession
from app.services import auth_service

SESSION_COOKIE = "mp_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthContext:
    user: User
    session: UserSession


def get_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    """Authenticates via the session cookie and enforces CSRF on state-changing methods."""
    token = request.cookies.get(SESSION_COOKIE)
    resolved = auth_service.resolve_session(db, token) if token else None
    if resolved is None:
        raise unauthenticated()
    user, session = resolved
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(sent, session.csrf_token):
            raise AppError(403, "csrf_failed", "Missing or invalid CSRF token.")
    return AuthContext(user, session)


def current_user(ctx: AuthContext = Depends(get_auth)) -> User:
    return ctx.user


def require_roles(*roles: str):
    """Role gate. Resource-level checks (e.g. manager owns client) are added in later stages."""
    def dep(ctx: AuthContext = Depends(get_auth)) -> User:
        if ctx.user.role not in roles:
            raise forbidden()
        return ctx.user
    return dep
