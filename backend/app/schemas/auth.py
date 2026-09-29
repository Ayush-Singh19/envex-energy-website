import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH


def check_password_strength(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password.encode()) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Use at most {PASSWORD_MAX_BYTES} bytes (about 70 characters).")
    if password.strip() != password:
        raise ValueError("The password can't start or end with a space.")
    return password


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return check_password_strength(v)


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class MeOut(AdminOut):
    company_name: str
