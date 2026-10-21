from datetime import datetime

from sqlalchemy import (BigInteger, Computed, DateTime, ForeignKey, ForeignKeyConstraint,
                        Identity, Index, String, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupervisorAssignment(Base):
    """CURRENT supervisor -> manager (-> client) mapping. One row per supervisor.
    History lives in assignment_history so FKs here never reference stale state."""
    __tablename__ = "supervisor_assignments"
    __table_args__ = (
        UniqueConstraint("supervisor_id", name="uq_supervisor_assignments_supervisor_id"),
        ForeignKeyConstraint(["supervisor_id", "supervisor_role"], ["users.id", "users.role"],
                             name="fk_supervisor_assignments_supervisor_is_supervisor"),
        ForeignKeyConstraint(["manager_id", "manager_role"], ["users.id", "users.role"],
                             name="fk_supervisor_assignments_manager_is_manager"),
        # The client's CURRENT manager must equal this row's manager (NULL client skips check).
        ForeignKeyConstraint(["client_id", "manager_id"], ["clients.id", "clients.manager_id"],
                             name="fk_supervisor_assignments_client_belongs_to_manager"),
        Index("ix_supervisor_assignments_manager_id", "manager_id"),
        Index("ix_supervisor_assignments_client_id", "client_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    supervisor_id: Mapped[int] = mapped_column(BigInteger)
    supervisor_role: Mapped[str] = mapped_column(String(20), Computed("'SUPERVISOR'::varchar", persisted=True))
    manager_id: Mapped[int] = mapped_column(BigInteger)
    manager_role: Mapped[str] = mapped_column(String(20), Computed("'MANAGER'::varchar", persisted=True))
    client_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AssignmentHistory(Base):
    __tablename__ = "assignment_history"
    __table_args__ = (Index("ix_assignment_history_supervisor_id", "supervisor_id"),
                      Index("ix_assignment_history_client_id", "client_id"))

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40))
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
