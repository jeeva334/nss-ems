from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: str
    full_name: str
    email: str
    mobile_number: str
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None
    # password_hash is intentionally not part of any response schema


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
