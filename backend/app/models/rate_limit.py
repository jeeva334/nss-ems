from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitEvent(Base):
    """One row per counted failure. Keys are stored hashed so identifiers (emails) are not kept in plaintext."""
    __tablename__ = "rate_limit_events"
    __table_args__ = (Index("ix_rate_limit_events_key_created", "key_hash", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
