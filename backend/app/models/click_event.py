from sqlalchemy import BigInteger, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ClickType
from app.db.base import Base
from app.models._types import CreatedAt, pg_enum


class ClickEvent(Base):
    """Anonymous CTA click counter. Holds no personal data by design (no IP, no user agent)."""

    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    type: Mapped[ClickType] = mapped_column(pg_enum(ClickType, "click_type"))
    page: Mapped[str | None] = mapped_column(String(300))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[CreatedAt]

    __table_args__ = (Index("ix_click_events_created_at_type", text("created_at DESC"), "type"),)
