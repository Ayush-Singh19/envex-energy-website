"""Enquiry submission: honeypot, duplicate detection, persistence, WhatsApp link."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Enquiry
from app.repositories.enquiry_repo import EnquiryRepository
from app.schemas.enquiry import EnquiryCreate, EnquiryCreated
from app.services import whatsapp_service
from app.services.notification_service import EnquiryAlert

logger = logging.getLogger(__name__)

THANK_YOU = "Thanks, we've received your enquiry. Opening WhatsApp so you can reach us directly."


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip_address: str | None
    user_agent: str | None


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    response: EnquiryCreated
    alert: EnquiryAlert | None  # None when nothing was stored (honeypot)


def _whatsapp_url(enquiry_id: uuid.UUID, data: EnquiryCreate, settings: Settings) -> str:
    text = whatsapp_service.build_enquiry_message(
        company_name=settings.company_name,
        name=data.name,
        project_type=data.project_type,
        system_size=data.system_size,
        location=data.location,
        reference=whatsapp_service.enquiry_reference(enquiry_id),
    )
    return whatsapp_service.build_whatsapp_url(settings.whatsapp_number, text)


async def submit_enquiry(
    session: AsyncSession, data: EnquiryCreate, meta: RequestMeta, settings: Settings
) -> SubmissionResult:
    if data.website:
        # Honeypot tripped: answer exactly like a success so the bot learns nothing.
        fake_id = uuid.uuid4()
        logger.info("enquiry_honeypot_triggered")
        return SubmissionResult(
            EnquiryCreated(
                id=fake_id, whatsapp_url=_whatsapp_url(fake_id, data, settings), message=THANK_YOU
            ),
            alert=None,
        )

    repo = EnquiryRepository(session)

    # Same phone inside the window: still store it (it may carry new details),
    # but flag it and point at the root enquiry so the team sees one thread.
    original: Enquiry | None = None
    if settings.duplicate_window_hours > 0:
        since = datetime.now(UTC) - timedelta(hours=settings.duplicate_window_hours)
        original = await repo.find_latest_by_phone_since(data.phone, since)
    duplicate_of = (original.duplicate_of or original.id) if original else None

    enquiry = Enquiry(
        id=uuid.uuid4(),
        name=data.name,
        company=data.company,
        phone=data.phone,
        email=data.email,
        location=data.location,
        project_type=data.project_type,
        system_size=data.system_size,
        message=data.message,
        consent=data.consent,
        is_duplicate=duplicate_of is not None,
        duplicate_of=duplicate_of,
        source_page=data.source_page,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent[:300] if meta.user_agent else None,
    )
    await repo.add(enquiry)
    await session.commit()

    reference = whatsapp_service.enquiry_reference(enquiry.id)
    logger.info(
        "enquiry_created",
        extra={
            "enquiry_id": str(enquiry.id),
            "project_type": enquiry.project_type,
            "is_duplicate": enquiry.is_duplicate,
        },
    )

    alert = EnquiryAlert(
        id=enquiry.id,
        reference=reference,
        name=enquiry.name,
        company=enquiry.company,
        phone=enquiry.phone,
        email=enquiry.email,
        location=enquiry.location,
        project_type=enquiry.project_type,
        system_size=enquiry.system_size,
        message=enquiry.message,
        is_duplicate=enquiry.is_duplicate,
        received_at=datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC"),
    )
    return SubmissionResult(
        EnquiryCreated(
            id=enquiry.id,
            whatsapp_url=_whatsapp_url(enquiry.id, data, settings),
            message=THANK_YOU,
        ),
        alert=alert,
    )
