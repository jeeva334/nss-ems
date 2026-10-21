from datetime import datetime

from sqlalchemy import (BigInteger, CheckConstraint, Computed, DateTime, ForeignKeyConstraint,
                        Identity, Index, String, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import CLIENT_STATUSES, sql_in
from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("client_code", name="uq_clients_client_code"),
        # Lets supervisor_assignments prove (client, manager) agree.
        UniqueConstraint("id", "manager_id", name="uq_clients_id_manager_id"),
        # Constant generated column + composite FK => manager_id must be a MANAGER user.
        ForeignKeyConstraint(["manager_id", "manager_role"], ["users.id", "users.role"],
                             name="fk_clients_manager_is_manager_users"),
        CheckConstraint(f"status IN ({sql_in(CLIENT_STATUSES)})", name="status_valid"),
        Index("ix_clients_manager_id", "manager_id"),
        Index("ix_clients_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    client_code: Mapped[str] = mapped_column(String(30))
    client_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    contact_name: Mapped[str | None] = mapped_column(String(150))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    # A single column => exactly one current Manager per client, by construction.
    manager_id: Mapped[int | None] = mapped_column(BigInteger)
    manager_role: Mapped[str] = mapped_column(String(20), Computed("'MANAGER'::varchar", persisted=True))
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
