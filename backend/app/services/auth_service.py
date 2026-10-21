from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import ACTIVE
from app.core.rate_limit import limiter
from app.core.security import (DUMMY_HASH, generate_token, hash_password, hash_token,
                               needs_rehash, verify_password)
from app.models import User, UserSession
from app.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_by_identifier(db: Session, identifier: str) -> User | None:
    ident = identifier.strip()
    col = User.email if "@" in ident else User.employee_id
    ident = ident.lower() if "@" in ident else ident.upper()
    return db.scalar(select(User).where(col == ident))


def login(db: Session, identifier: str, password: str, client_ip: str) -> tuple[User, str, UserSession] | None:
    """Returns (user, raw_session_token, session) or None. Rate-limit errors raise AppError(429)."""
    s = get_settings()
    id_key, ip_key = f"login:id:{identifier.strip().lower()}", f"login:ip:{client_ip}"
    limiter.check(id_key, s.login_max_failures, s.login_window_seconds)
    limiter.check(ip_key, s.login_max_failures * 4, s.login_window_seconds)

    user = _find_by_identifier(db, identifier)
    usable = user is not None and user.status == ACTIVE and user.password_hash is not None
    # Always run one Argon2 verification so timing doesn't reveal account existence.
    ok = verify_password(user.password_hash if usable else DUMMY_HASH, password)
    if not (usable and ok):
        limiter.hit(id_key, s.login_window_seconds)
        limiter.hit(ip_key, s.login_window_seconds)
        audit_service.record(db, "auth.login_failed", None, "user", user.id if user else None,
                             {"reason": "invalid_credentials_or_state"})
        db.commit()
        return None

    limiter.clear(id_key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = _now()
    token, session = create_session(db, user)
    audit_service.record(db, "auth.login_success", user.id, "user", user.id)
    db.commit()
    return user, token, session


def create_session(db: Session, user: User) -> tuple[str, UserSession]:
    token = generate_token()  # fresh identifier on every login => no session fixation
    session = UserSession(id=hash_token(token), user_id=user.id, csrf_token=generate_token(),
                          expires_at=_now() + timedelta(hours=get_settings().session_absolute_hours))
    db.add(session)
    db.flush()
    return token, session


def resolve_session(db: Session, token: str) -> tuple[User, UserSession] | None:
    s, now = get_settings(), _now()
    sess = db.get(UserSession, hash_token(token))
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
        return None
    if now - sess.last_seen_at > timedelta(minutes=s.session_idle_minutes):
        return None
    user = db.get(User, sess.user_id)
    if user is None or user.status != ACTIVE:
        return None
    if now - sess.last_seen_at > timedelta(seconds=60):
        sess.last_seen_at = now
        db.commit()
    return user, sess


def revoke_session(db: Session, session_id: str) -> None:
    db.execute(update(UserSession).where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
               .values(revoked_at=_now()))


def revoke_user_sessions(db: Session, user_id: int) -> None:
    """Call (inside the same transaction) whenever a user is deactivated."""
    db.execute(update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
               .values(revoked_at=_now()))
