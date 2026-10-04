"""Admin enquiry management: list, detail with history, status/follow-up updates, notes."""

import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import STATUS_LABELS, AuditAction, EnquiryStatus
from app.core.errors import NotFoundError
from app.models import AdminUser, AuditLog, Enquiry, EnquiryNote
from app.repositories.audit_repo import AuditRepository
from app.repositories.enquiry_repo import EnquiryFilters, EnquiryRepository
from app.schemas.admin_enquiry import (
    EnquiryDetail,
    EnquiryItem,
    EnquiryPage,
    EnquiryUpdate,
    HistoryEntry,
    RelatedEnquiry,
)
from app.schemas.note import NoteIn, NoteOut
from app.services import whatsapp_service

logger = logging.getLogger(__name__)

ENQUIRY_ENTITY = "enquiry"


def to_item(e: Enquiry, settings: Settings) -> EnquiryItem:
    reference = whatsapp_service.enquiry_reference(e.id)
    reply = whatsapp_service.build_customer_reply_message(
        company_name=settings.company_name,
        name=e.name,
        project_type=e.project_type,
        reference=reference,
    )
    subject = quote(f"Your {e.project_type.lower()} enquiry ({reference})", safe="")
    return EnquiryItem(
        id=e.id,
        reference=reference,
        name=e.name,
        company=e.company,
        phone=e.phone,
        email=e.email,
        location=e.location,
        project_type=e.project_type,
        system_size=e.system_size,
        message=e.message,
        status=e.status,
        follow_up_date=e.follow_up_date,
        is_duplicate=e.is_duplicate,
        duplicate_of=e.duplicate_of,
        created_at=e.created_at,
        tel_url=f"tel:{e.phone}",
        whatsapp_url=whatsapp_service.customer_whatsapp_url(e.phone, reply),
        mailto_url=f"mailto:{e.email}?subject={subject}",
    )


def local_day_start(d: date, settings: Settings) -> datetime:
    return datetime.combine(d, time.min, tzinfo=settings.tz)


async def list_enquiries(
    session: AsyncSession,
    *,
    status: EnquiryStatus | None,
    q: str | None,
    project_type: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
    settings: Settings,
) -> EnquiryPage:
    repo = EnquiryRepository(session)
    filters = EnquiryFilters(
        status=status,
        q=q.strip() if q and q.strip() else None,
        project_type=project_type,
        created_from=local_day_start(date_from, settings) if date_from else None,
        created_to=local_day_start(date_to + timedelta(days=1), settings) if date_to else None,
    )
    rows, total = await repo.list(filters, offset=(page - 1) * page_size, limit=page_size)
    by_status = await repo.count_by_status()
    counts = {s.value: by_status.get(s, 0) for s in EnquiryStatus}
    counts["all"] = sum(n for s, n in by_status.items() if s != EnquiryStatus.NOT_RELEVANT)
    return EnquiryPage(
        items=[to_item(e, settings) for e in rows],
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
    )


def _fmt_day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _label(value: str) -> str:
    try:
        return STATUS_LABELS[EnquiryStatus(value)]
    except ValueError:
        return value


def _history_lines(entry: AuditLog) -> list[str]:
    old, new = entry.old_value or {}, entry.new_value or {}
    lines: list[str] = []
    if entry.action == AuditAction.UPDATE.value:
        if "status" in new:
            lines.append(f"Status changed from {_label(old['status'])} to {_label(new['status'])}")
        if "follow_up_date" in new:
            value = new["follow_up_date"]
            lines.append(
                f"Follow-up set for {_fmt_day(date.fromisoformat(value))}"
                if value
                else "Follow-up cleared"
            )
    elif entry.action == AuditAction.ADD_NOTE.value:
        lines.append("Note added")
    return lines


async def get_detail(
    session: AsyncSession, enquiry_id: uuid.UUID, settings: Settings
) -> EnquiryDetail:
    repo = EnquiryRepository(session)
    enquiry = await repo.get(enquiry_id, with_notes=True)
    if enquiry is None:
        raise NotFoundError("Enquiry")

    history: list[HistoryEntry] = []
    for entry in await AuditRepository(session).list_for_entity(ENQUIRY_ENTITY, enquiry.id):
        by = entry.admin.full_name if entry.admin else None
        history += [HistoryEntry(at=entry.created_at, text=t, by=by) for t in _history_lines(entry)]
    received = "Repeat enquiry received" if enquiry.is_duplicate else "Enquiry received"
    history.append(HistoryEntry(at=enquiry.created_at, text=f"{received} from the website"))

    original = await repo.get(enquiry.duplicate_of) if enquiry.duplicate_of else None
    newer = await repo.latest_repeat_of(enquiry.id)
    return EnquiryDetail(
        **to_item(enquiry, settings).model_dump(),
        notes=[
            NoteOut(
                id=n.id,
                note=n.note,
                created_at=n.created_at,
                admin_name=n.admin.full_name if n.admin else None,
            )
            for n in enquiry.notes
        ],
        history=history,
        original=RelatedEnquiry(id=original.id, created_at=original.created_at)
        if original
        else None,
        newer=RelatedEnquiry(id=newer.id, created_at=newer.created_at) if newer else None,
    )


async def update_enquiry(
    session: AsyncSession,
    enquiry_id: uuid.UUID,
    data: EnquiryUpdate,
    admin: AdminUser,
    ip: str | None,
    settings: Settings,
) -> EnquiryDetail:
    enquiry = await EnquiryRepository(session).get(enquiry_id)
    if enquiry is None:
        raise NotFoundError("Enquiry")

    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    if data.status is not None and data.status != enquiry.status:
        old["status"], new["status"] = enquiry.status.value, data.status.value
        enquiry.status = data.status
        enquiry.status_changed_at = datetime.now(UTC)
    if "follow_up_date" in data.model_fields_set and data.follow_up_date != enquiry.follow_up_date:
        old["follow_up_date"] = (
            enquiry.follow_up_date.isoformat() if enquiry.follow_up_date else None
        )
        new["follow_up_date"] = data.follow_up_date.isoformat() if data.follow_up_date else None
        enquiry.follow_up_date = data.follow_up_date

    if new:
        await AuditRepository(session).add(
            admin_id=admin.id,
            action=AuditAction.UPDATE,
            entity_type=ENQUIRY_ENTITY,
            entity_id=enquiry.id,
            old_value=old,
            new_value=new,
            ip_address=ip,
        )
        await session.commit()
        logger.info(
            "enquiry_updated",
            extra={"enquiry_id": str(enquiry.id), "fields": sorted(new), "admin_id": str(admin.id)},
        )
    session.expire_all()
    return await get_detail(session, enquiry_id, settings)


async def add_note(
    session: AsyncSession,
    enquiry_id: uuid.UUID,
    data: NoteIn,
    admin: AdminUser,
    ip: str | None,
    settings: Settings,
) -> EnquiryDetail:
    repo = EnquiryRepository(session)
    enquiry = await repo.get(enquiry_id)
    if enquiry is None:
        raise NotFoundError("Enquiry")
    note = await repo.add_note(
        EnquiryNote(enquiry_id=enquiry.id, admin_id=admin.id, note=data.note)
    )
    await AuditRepository(session).add(
        admin_id=admin.id,
        action=AuditAction.ADD_NOTE,
        entity_type=ENQUIRY_ENTITY,
        entity_id=enquiry.id,
        new_value={"note_id": str(note.id)},  # the note text stays out of the audit log
        ip_address=ip,
    )
    await session.commit()
    session.expire_all()
    return await get_detail(session, enquiry_id, settings)


async def delete_enquiry(
    session: AsyncSession, enquiry_id: uuid.UUID, admin: AdminUser, ip: str | None
) -> None:
    """Erase an enquiry on the customer's request (notes go with it).

    The audit entry keeps only the reference and status, never the personal data, so the
    deletion itself is accountable without undoing it.
    """
    repo = EnquiryRepository(session)
    enquiry = await repo.get(enquiry_id)
    if enquiry is None:
        raise NotFoundError("Enquiry")
    reference = whatsapp_service.enquiry_reference(enquiry.id)
    status = enquiry.status.value
    await repo.delete(enquiry)
    await AuditRepository(session).add(
        admin_id=admin.id,
        action=AuditAction.DELETE,
        entity_type=ENQUIRY_ENTITY,
        entity_id=enquiry_id,
        old_value={"reference": reference, "status": status},
        ip_address=ip,
    )
    await session.commit()
    logger.info("enquiry_deleted", extra={"enquiry_id": str(enquiry_id), "admin_id": str(admin.id)})
