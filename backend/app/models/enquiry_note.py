import uuid

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._types import CreatedAt


class EnquiryNote(Base):
    __tablename__ = "enquiry_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enquiries.id", ondelete="CASCADE")
    )
    # SET NULL keeps the note if an admin account is ever deleted.
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[CreatedAt]

    enquiry: Mapped["Enquiry"] = relationship(back_populates="notes")  # noqa: F821
    admin: Mapped["AdminUser | None"] = relationship(lazy="joined")  # noqa: F821

    __table_args__ = (
        Index("ix_enquiry_notes_enquiry_id_created_at", "enquiry_id", text("created_at DESC")),
    )
