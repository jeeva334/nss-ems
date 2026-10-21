from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import ACTIVE, PENDING
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.core.security import enforce_password_policy, generate_token, hash_password, hash_token
from app.models import Invitation, User
from app.schemas.user import DeliveryOut, InvitationOut
from app.services import audit_service, email_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def state_of(inv: Invitation, now: datetime | None = None) -> str:
    now = now or _now()
    if inv.consumed_at:
        return "ACCEPTED"
    if inv.revoked_at:
        return "REVOKED"
    if inv.expires_at <= now:
        return "EXPIRED"
    return "SENT" if inv.sent_at else "SEND_FAILED"


def to_out(inv: Invitation) -> InvitationOut:
    return InvitationOut(state=state_of(inv), created_at=inv.created_at, expires_at=inv.expires_at,
                         sent_at=inv.sent_at, send_error=inv.send_error)


def latest_for(db: Session, user_id: int) -> Invitation | None:
    return db.scalar(select(Invitation).where(Invitation.user_id == user_id)
                     .order_by(Invitation.id.desc()).limit(1))


def revoke_active(db: Session, user_id: int) -> int:
    res = db.execute(update(Invitation).where(Invitation.user_id == user_id, Invitation.consumed_at.is_(None),
                                              Invitation.revoked_at.is_(None)).values(revoked_at=_now()))
    return res.rowcount


def issue(db: Session, user: User, actor_id: int) -> tuple[Invitation, str]:
    """Revokes older live invitations and stores a new hashed one. Caller commits."""
    if user.status != PENDING:
        raise AppError(409, "user_not_pending", "Invitations can only be sent to accounts awaiting activation.")
    key = f"invite:user:{user.id}"
    limiter.check(key, 5, 3600)
    limiter.hit(key, 3600)
    revoke_active(db, user.id)
    token = generate_token()
    inv = Invitation(user_id=user.id, token_hash=hash_token(token),
                     expires_at=_now() + timedelta(hours=get_settings().invitation_ttl_hours))
    db.add(inv)
    db.flush()
    audit_service.record(db, "invitation.issue", actor_id, "user", user.id, {"invitation_id": inv.id})
    return inv, token


def deliver(db: Session, user: User, inv: Invitation, token: str, actor_id: int) -> DeliveryOut:
    """Sends AFTER the invitation row is committed, so a provider failure never loses the account."""
    s = get_settings()
    sender = email_service.get_email_sender()
    link = f"{s.frontend_base_url.rstrip('/')}/activate#token={token}"  # fragment: never sent to servers/logs
    try:
        sender.send(user.email, "Activate your Manpower Portal account",
                    email_service.render_invitation(user.full_name, link, s.invitation_ttl_hours))
    except email_service.EmailDeliveryError as e:
        inv.send_error = e.code[:300]
        audit_service.record(db, "invitation.send_failed", actor_id, "user", user.id, {"error": e.code})
        db.commit()
        return DeliveryOut(status="failed", provider=sender.provider, error=e.code)
    inv.sent_at, inv.send_error = _now(), None
    audit_service.record(db, "invitation.sent", actor_id, "user", user.id, {"provider": sender.provider})
    db.commit()
    return DeliveryOut(status="sent", provider=sender.provider)


def issue_and_send(db: Session, user: User, actor_id: int):
    try:
        inv, token = issue(db, user, actor_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "invitation_conflict", "Another invitation change is in progress. Try again.") from None
    return inv, deliver(db, user, inv, token, actor_id)


def revoke(db: Session, user: User, actor_id: int) -> None:
    if revoke_active(db, user.id) == 0:
        raise AppError(409, "no_active_invitation", "There is no active invitation to revoke.")
    audit_service.record(db, "invitation.revoke", actor_id, "user", user.id)
    db.commit()


def activate(db: Session, token: str, password: str, client_ip: str) -> None:
    key = f"activate:ip:{client_ip}"
    limiter.check(key, 10, 900)
    enforce_password_policy(password)
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)).with_for_update())
    invalid = AppError(400, "invitation_invalid", "This invitation link is invalid or has already been used.")
    if inv is None or inv.consumed_at or inv.revoked_at:
        limiter.hit(key, 900)
        raise invalid
    if inv.expires_at <= _now():
        raise AppError(400, "invitation_expired", "This invitation has expired. Ask an administrator to send a new one.")
    user = db.scalar(select(User).where(User.id == inv.user_id).with_for_update())
    if user is None or user.status != PENDING:
        raise invalid
    inv.consumed_at = _now()
    user.password_hash = hash_password(password)
    user.status = ACTIVE
    audit_service.record(db, "auth.activate", user.id, "user", user.id)
    db.commit()
