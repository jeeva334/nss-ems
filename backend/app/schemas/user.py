import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.auth import UserOut

Role = Literal["ADMIN", "MANAGER", "SUPERVISOR"]


def normalize_mobile(v: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", v)
    if not re.fullmatch(r"\+?[0-9]{7,15}", cleaned):
        raise ValueError("Enter a valid mobile number (7-15 digits, optional leading +).")
    return cleaned


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    mobile_number: str
    email: EmailStr
    role: Role

    _name = field_validator("full_name")(lambda v: v.strip() if len(v.strip()) >= 2 else (_ for _ in ()).throw(ValueError("Enter the full name.")))
    _mobile = field_validator("mobile_number")(normalize_mobile)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # role/employee_id/status cannot be changed here

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    mobile_number: str | None = None
    email: EmailStr | None = None

    @field_validator("mobile_number")
    @classmethod
    def _mobile(cls, v):
        return normalize_mobile(v) if v is not None else v

    @model_validator(mode="after")
    def _non_empty(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self


class StatusUpdate(BaseModel):
    status: Literal["ACTIVE", "INACTIVE"]


class InvitationOut(BaseModel):
    state: Literal["SENT", "SEND_FAILED", "EXPIRED", "REVOKED", "ACCEPTED"]
    created_at: datetime
    expires_at: datetime
    sent_at: datetime | None = None
    send_error: str | None = None


class DeliveryOut(BaseModel):
    status: Literal["sent", "failed"]
    provider: str
    error: str | None = None


class InvitationResult(BaseModel):
    invitation: InvitationOut
    delivery: DeliveryOut


class UserCreateOut(InvitationResult):
    user: UserOut


class UserDetailOut(BaseModel):
    user: UserOut
    invitation: InvitationOut | None = None
    assignments: dict


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class ActivateRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def _match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self
