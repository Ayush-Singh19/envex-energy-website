from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ClickType


class ClickEventIn(BaseModel):
    """An anonymous CTA click. Deliberately has no field that could carry personal data."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    type: ClickType
    page: str | None = Field(default=None, max_length=300)
    utm_source: str | None = Field(default=None, max_length=100)

    @field_validator("page")
    @classmethod
    def _path_only(cls, v: str | None) -> str | None:
        # Keep the path, drop any query string or fragment (they can carry personal data).
        if not v:
            return None
        return v.split("?", 1)[0].split("#", 1)[0] or None

    @field_validator("utm_source")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None
