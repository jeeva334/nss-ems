from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.constants import ADMIN, MANAGER, SUPERVISOR
from app.db.session import get_db
from app.models import User
from app.schemas.client import (ClientCreate, ClientDetailOut, ClientListOut, ClientOut, ClientStatusUpdate,
                                ClientUpdate, ManagerAssign)
from app.services import client_service

router = APIRouter(prefix="/clients", tags=["clients"])
admin_only = require_roles(ADMIN)


@router.get("", response_model=ClientListOut)
def list_clients(q: str | None = Query(None, max_length=100), status: Literal["ACTIVE", "INACTIVE"] | None = None,
                 manager_id: int | None = None, unassigned: bool = False,
                 page: int = Query(1, ge=1, le=100000), page_size: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), actor: User = Depends(require_roles(ADMIN, MANAGER))):
    items, total = client_service.list_clients(db, actor, q, status, manager_id, unassigned, page, page_size)
    return ClientListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return client_service.create_client(db, body, admin)


@router.get("/{client_id}", response_model=ClientDetailOut)
def get_client(client_id: int, db: Session = Depends(get_db),
               actor: User = Depends(require_roles(ADMIN, MANAGER, SUPERVISOR))):
    from app.models import User as U
    c = client_service.get_or_404(db, client_id)
    client_service.assert_can_view(db, actor, c)
    sups = client_service.supervisors_on_client(db, c.id) if actor.role != SUPERVISOR else []
    return ClientDetailOut(client=client_service.to_out(c, db.get(U, c.manager_id) if c.manager_id else None), supervisors=sups)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, body: ClientUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return client_service.update_client(db, client_service.get_or_404(db, client_id), body, admin)


@router.patch("/{client_id}/status", response_model=ClientOut)
def update_status(client_id: int, body: ClientStatusUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return client_service.set_status(db, client_id, body.status, admin)


@router.put("/{client_id}/manager", response_model=ClientOut)
def put_manager(client_id: int, body: ManagerAssign, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return client_service.assign_manager(db, client_id, body.manager_id, body.reassign, admin)
