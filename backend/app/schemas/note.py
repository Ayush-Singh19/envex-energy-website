import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NoteIn(BaseModel):
    note: str = Field(max_length=2000)

    @field_validator("note")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Write something before adding the note.")
        return v


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    note: str
    created_at: datetime
    admin_name: str | None = None
