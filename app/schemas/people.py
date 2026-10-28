import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_PASSWORD_LENGTH = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _empty_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _check_email(value):
    if value is not None and not _EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value.lower() if value else value


# ----- Suppliers ---------------------------------------------------------------


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=150)
    note: Optional[str] = Field(default=None, max_length=500)

    _clean = field_validator("name", "contact_name", "phone", "email", "note", mode="before")(_empty_to_none)
    _email = field_validator("email")(_check_email)


class SupplierUpdate(SupplierCreate):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    note: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ----- Users -------------------------------------------------------------------

Role = Literal["admin", "cashier"]


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(max_length=150)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    role: Role = "cashier"

    _clean = field_validator("full_name", "username", "email", mode="before")(_empty_to_none)
    _email = field_validator("email")(_check_email)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    role: Optional[Role] = None
    is_active: Optional[bool] = None

    _clean = field_validator("full_name", "email", mode="before")(_empty_to_none)
    _email = field_validator("email")(_check_email)


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str
    role: str
    is_active: bool
