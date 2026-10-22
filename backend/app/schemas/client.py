import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.user import normalize_mobile


def _blank_to_none(v):
    return None if isinstance(v, str) and not v.strip() else v


class ClientFields(BaseModel):
    client_name: str = Field(min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=150)
    contact_email: EmailStr | None = None
    contact_phone: str | None = None

    @field_validator("address", "contact_name", "contact_email", "contact_phone", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v):
        return normalize_mobile(v) if v else v

    @field_validator("client_name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Enter the client name.")
        return v


class ClientCreate(ClientFields):
    client_code: str

    @field_validator("client_code")
    @classmethod
    def _code(cls, v):
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,29}", v):
            raise ValueError("Use 2-30 letters, digits, hyphens or underscores (e.g. ACME-01).")
        return v


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # code, manager and status have dedicated paths
    client_name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=150)
    contact_email: EmailStr | None = None
    contact_phone: str | None = None

    @field_validator("address", "contact_name", "contact_email", "contact_phone", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v):
        return normalize_mobile(v) if v else v


class ClientStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "INACTIVE"]


class ManagerAssign(BaseModel):
    manager_id: int | None
    reassign: bool = False  # must be true to move a client away from its current Manager


class SupervisorManagerAssign(BaseModel):
    manager_id: int | None
    clear_client: bool = False  # must be true to drop a client that belongs to the old Manager


class SupervisorClientAssign(BaseModel):
    client_id: int | None


class PersonBrief(BaseModel):
    id: int
    employee_id: str
    full_name: str


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_code: str
    client_name: str
    address: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    manager_id: int | None = None
    manager: PersonBrief | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ClientListOut(BaseModel):
    items: list[ClientOut]
    total: int
    page: int
    page_size: int


class ClientDetailOut(BaseModel):
    client: ClientOut
    supervisors: list[PersonBrief]
