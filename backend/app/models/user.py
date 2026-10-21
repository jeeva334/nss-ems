from datetime import datetime

from sqlalchemy import (BigInteger, CheckConstraint, DateTime, ForeignKey, Identity,
                        Index, String, UniqueConstraint, func, text)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ROLES, USER_STATUSES, sql_in
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_users_employee_id"),
        UniqueConstraint("email", name="uq_users_email"),
        # Target for composite FKs that must guarantee a referenced user's role.
        UniqueConstraint("id", "role", name="uq_users_id_role"),
        CheckConstraint(f"role IN ({sql_in(ROLES)})", name="role_valid"),
        CheckConstraint(f"status IN ({sql_in(USER_STATUSES)})", name="status_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("employee_id ~ '^EMP[0-9]{4,}$'", name="employee_id_format"),
        CheckConstraint("status <> 'ACTIVE' OR password_hash IS NOT NULL",
                        name="active_requires_password"),
        Index("ix_users_role", "role"),
        Index("ix_users_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Allocated by PostgreSQL (sequence), never by counting rows.
    employee_id: Mapped[str] = mapped_column(String(20), server_default=text("next_employee_id()"))
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254))
    mobile_number: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default="PENDING")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
