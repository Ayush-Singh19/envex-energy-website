import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EnquiryStatus
from app.db.base import Base
from app.models._types import CreatedAt, pg_enum


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(20))  # E.164, e.g. +919876543210
    email: Mapped[str] = mapped_column(String(254))
    location: Mapped[str] = mapped_column(String(160))
    project_type: Mapped[str] = mapped_column(String(60))
    system_size: Mapped[str | None] = mapped_column(String(60))
    message: Mapped[str | None] = mapped_column(Text)
    consent: Mapped[bool] = mapped_column(Boolean)

    status: Mapped[EnquiryStatus] = mapped_column(
        pg_enum(EnquiryStatus, "enquiry_status"),
        default=EnquiryStatus.NEW,
        server_default=EnquiryStatus.NEW.value,
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enquiries.id", ondelete="SET NULL")
    )

    source_page: Mapped[str | None] = mapped_column(String(300))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    notes: Mapped[list["EnquiryNote"]] = relationship(  # noqa: F821
        back_populates="enquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(EnquiryNote.created_at)",
    )

    __table_args__ = (
        Index("ix_enquiries_status_created_at", "status", text("created_at DESC")),
        Index("ix_enquiries_phone_created_at", "phone", text("created_at DESC")),
        Index(
            "ix_enquiries_follow_up_date",
            "follow_up_date",
            postgresql_where=text("follow_up_date IS NOT NULL"),
        ),
        Index("ix_enquiries_project_type", "project_type"),
        Index("ix_enquiries_created_at", text("created_at DESC")),
    )
