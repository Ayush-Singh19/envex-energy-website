import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.passwords import password_problem


def check_password_strength(password: str, email: str | None = None) -> str:
    problem = password_problem(password, email)
    if problem:
        raise ValueError(problem)
    return password


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=254)
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        # Email-specific checks run in the service, where the admin is known.
        return check_password_strength(v)


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class MeOut(AdminOut):
    company_name: str
    must_change_password: bool = False
