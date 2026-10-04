"""Admin-facing enquiry shapes.

Only what the client uses day to day is exposed. UTM fields, IP address and user agent
stay in the database but are not sent to the admin page.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.core.constants import EnquiryStatus
from app.schemas.note import NoteOut


class EnquiryItem(BaseModel):
    id: uuid.UUID
    reference: str
    name: str
    company: str | None
    phone: str
    email: str
    location: str
    project_type: str
    system_size: str | None
    message: str | None
    status: EnquiryStatus
    follow_up_date: date | None
    is_duplicate: bool
    duplicate_of: uuid.UUID | None
    created_at: datetime
    # Ready-to-use links so the page never builds them from raw data.
    tel_url: str
    whatsapp_url: str
    mailto_url: str


class HistoryEntry(BaseModel):
    at: datetime
    text: str
    by: str | None = None


class RelatedEnquiry(BaseModel):
    id: uuid.UUID
    created_at: datetime


class EnquiryDetail(EnquiryItem):
    notes: list[NoteOut]
    history: list[HistoryEntry]
    original: RelatedEnquiry | None  # the earlier enquiry this one repeats
    newer: RelatedEnquiry | None  # the latest repeat of this enquiry


class EnquiryPage(BaseModel):
    items: list[EnquiryItem]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]  # per status, plus "all" (everything except not_relevant)


class EnquiryUpdate(BaseModel):
    """PATCH body. Send only what changes; ``follow_up_date: null`` clears the date."""

    model_config = ConfigDict(extra="forbid")

    status: EnquiryStatus | None = None
    follow_up_date: date | None = None
