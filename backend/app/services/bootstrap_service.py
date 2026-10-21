from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ACTIVE, ADMIN
from app.core.errors import AppError
from app.core.security import enforce_password_policy, hash_password
from app.models import User
from app.services import audit_service


def create_initial_admin(db: Session, full_name: str, email: str, mobile: str, password: str) -> User:
    """One-time bootstrap, invoked only from the CLI script. Refuses if any Admin exists."""
    if db.scalar(select(User.id).where(User.role == ADMIN).limit(1)) is not None:
        raise AppError(409, "admin_exists", "An Admin already exists; bootstrap is disabled.")
    enforce_password_policy(password)
    user = User(full_name=full_name.strip(), email=email.strip().lower(), mobile_number=mobile.strip(),
                role=ADMIN, status=ACTIVE, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    audit_service.record(db, "admin.bootstrap", user.id, "user", user.id)
    db.commit()
    return user
