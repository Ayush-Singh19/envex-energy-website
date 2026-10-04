"""Public enquiry payloads.

Validation mirrors the frontend's ``_submitEnquiry`` rules and messages so the
user sees the same wording whichever side catches the problem.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.core.constants import EMAIL_PATTERN, PROJECT_TYPES
from app.core.phone import normalise_phone


class EnquiryCreate(BaseModel):
    # validate_default: a missing required field must hit its validator (and its message).
    # extra="forbid": unknown fields are rejected, not silently dropped.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", validate_default=True)

    name: str = Field(default="", max_length=120)
    company: str | None = Field(default=None, max_length=160)
    phone: str = Field(default="", max_length=30, description="Any common format; stored as E.164")
    email: str = Field(default="", max_length=254)
    location: str = Field(default="", max_length=160)
    project_type: str = Field(default="", max_length=60, examples=[PROJECT_TYPES[1]])
    system_size: str | None = Field(default=None, max_length=60)
    message: str | None = Field(default=None, max_length=4000)
    consent: StrictBool = False  # JSON true only; "true" or 1 are rejected

    # Honeypot: hidden from people, filled in by naive bots. Must be empty.
    website: str | None = Field(default=None, max_length=300)

    source_page: str | None = Field(default=None, max_length=300)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)

    @field_validator(
        "company",
        "system_size",
        "message",
        "website",
        "source_page",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    )
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("name")
    @classmethod
    def _name_required(cls, v: str) -> str:
        if not v:
            raise ValueError("Please enter your name.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalise_phone(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL_PATTERN.fullmatch(v):
            raise ValueError("Please enter a valid email address.")
        return v

    @field_validator("location")
    @classmethod
    def _location_required(cls, v: str) -> str:
        if not v:
            raise ValueError("Please tell us where the project is.")
        return v

    @field_validator("project_type")
    @classmethod
    def _known_project_type(cls, v: str) -> str:
        if v not in PROJECT_TYPES:
            raise ValueError("Please choose the type of project.")
        return v

    @field_validator("consent")
    @classmethod
    def _consent_given(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please agree to be contacted about your enquiry.")
        return v


class EnquiryCreated(BaseModel):
    id: uuid.UUID
    whatsapp_url: str
    message: str
