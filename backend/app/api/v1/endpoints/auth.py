from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, AuthContext, get_auth
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, SessionOut, UserOut
from app.services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(SESSION_COOKIE, token, max_age=s.session_absolute_hours * 3600, httponly=True,
                        secure=s.secure_cookies, samesite=s.cookie_samesite, path="/")


@router.post("/login", response_model=SessionOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    # Rotation: retire any session presented with this request before issuing a new one.
    old = request.cookies.get(SESSION_COOKIE)
    result = auth_service.login(db, body.identifier, body.password, request.client.host if request.client else "?")
    if result is None:
        raise AppError(401, "invalid_credentials", "Invalid credentials.")
    user, token, session = result
    if old:
        auth_service.revoke_session(db, hash_token(old))
        db.commit()
    _set_cookie(response, token)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)


@router.post("/logout", status_code=204)
def logout(response: Response, ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)):
    auth_service.revoke_session(db, ctx.session.id)
    audit_service.record(db, "auth.logout", ctx.user.id, "user", ctx.user.id)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=SessionOut)
def me(ctx: AuthContext = Depends(get_auth)):
    return SessionOut(user=UserOut.model_validate(ctx.user), csrf_token=ctx.session.csrf_token)
