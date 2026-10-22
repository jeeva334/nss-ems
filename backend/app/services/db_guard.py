from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.errors import AppError

RETRYABLE = {"40P01", "40001"}  # deadlock detected / serialization failure


@contextmanager
def conflict_guard(db: Session):
    """Rolls back (releasing row locks) on any failure and turns DB-level conflicts into clean 409s."""
    try:
        yield
    except AppError:
        db.rollback()
        raise
    except DBAPIError as e:
        db.rollback()
        code = getattr(e.orig, "sqlstate", None) or ""
        if code.startswith("23") or code in RETRYABLE:
            raise AppError(409, "conflict", "This change conflicts with another recent change. Reload and try again.") from None
        raise
