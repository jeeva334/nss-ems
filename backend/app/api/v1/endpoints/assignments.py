from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.constants import ADMIN
from app.db.session import get_db
from app.models import User
from app.schemas.client import SupervisorClientAssign, SupervisorManagerAssign
from app.services import assignment_service, user_service

router = APIRouter(prefix="/users", tags=["assignments"])
admin_only = require_roles(ADMIN)


@router.put("/{user_id}/manager")
def map_supervisor_to_manager(user_id: int, body: SupervisorManagerAssign, db: Session = Depends(get_db),
                              admin: User = Depends(admin_only)):
    """Separate, explicit action: maps (or remaps / unmaps) a Supervisor's Manager."""
    return assignment_service.map_manager(db, user_id, body.manager_id, body.clear_client, admin)


@router.put("/{user_id}/client")
def assign_supervisor_client(user_id: int, body: SupervisorClientAssign, db: Session = Depends(get_db),
                             admin: User = Depends(admin_only)):
    """The Manager is never supplied here: it is taken from the existing mapping and validated."""
    return assignment_service.assign_client(db, user_id, body.client_id, admin)


@router.get("/{user_id}/assignments")
def get_assignments(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    user = user_service.get_or_404(db, user_id)
    return {"assignments": user_service.assignments_for(db, user), "history": assignment_service.history_for(db, user)}
