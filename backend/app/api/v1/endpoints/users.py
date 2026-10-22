from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.constants import ADMIN
from app.db.session import get_db
from app.models import User
from app.schemas.auth import UserOut
from app.schemas.user import (InvitationResult, StatusUpdate, UserCreate, UserCreateOut,
                              UserDetailOut, UserListOut, UserUpdate)
from app.services import invitation_service, user_service

router = APIRouter(prefix="/users", tags=["users"])
admin_only = require_roles(ADMIN)


@router.get("", response_model=UserListOut)
def list_users(q: str | None = Query(None, max_length=100),
               role: Literal["ADMIN", "MANAGER", "SUPERVISOR"] | None = None,
               status: Literal["PENDING", "ACTIVE", "INACTIVE"] | None = None,
               mapped: bool | None = None,
               page: int = Query(1, ge=1, le=100000), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), _: User = Depends(admin_only)):
    items, total = user_service.list_users(db, q, role, status, page, page_size, mapped)
    return UserListOut(items=[UserOut.model_validate(u) for u in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserCreateOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user, inv, delivery = user_service.create_user(db, body, admin)
    return UserCreateOut(user=UserOut.model_validate(user), invitation=invitation_service.to_out(inv), delivery=delivery)


@router.get("/{user_id}", response_model=UserDetailOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    user = user_service.get_or_404(db, user_id)
    inv = invitation_service.latest_for(db, user.id)
    return UserDetailOut(user=UserOut.model_validate(user), invitation=invitation_service.to_out(inv) if inv else None,
                         assignments=user_service.assignments_for(db, user))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return user_service.update_user(db, user_service.get_or_404(db, user_id), body, admin)


@router.patch("/{user_id}/status", response_model=UserOut)
def update_status(user_id: int, body: StatusUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return user_service.set_status(db, user_service.get_or_404(db, user_id), body.status, admin)


@router.post("/{user_id}/invitations", response_model=InvitationResult, status_code=201)
def send_invitation(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = user_service.get_or_404(db, user_id)
    inv, delivery = invitation_service.issue_and_send(db, user, admin.id)
    return InvitationResult(invitation=invitation_service.to_out(inv), delivery=delivery)


@router.post("/{user_id}/invitations/revoke", status_code=204)
def revoke_invitation(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    invitation_service.revoke(db, user_service.get_or_404(db, user_id), admin.id)
    return Response(status_code=204)
