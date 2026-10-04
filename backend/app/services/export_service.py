"""CSV export of every enquiry, streamed so memory stays flat as the table grows."""

import csv
import io
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import STATUS_LABELS, AuditAction
from app.db.session import SessionLocal
from app.models import AdminUser
from app.repositories.audit_repo import AuditRepository
from app.repositories.enquiry_repo import EnquiryRepository
from app.services.whatsapp_service import enquiry_reference

COLUMNS = [
    "Reference",
    "Received",
    "Name",
    "Company",
    "Phone",
    "Email",
    "Location",
    "Project type",
    "System size",
    "Status",
    "Follow-up",
    "Repeat of",
    "Message",
    "Latest note",
]

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: object) -> str:
    """Stop spreadsheet apps from running user text as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def filename(settings: Settings) -> str:
    return f"envex-leads-{datetime.now(settings.tz):%Y-%m-%d}.csv"


async def record_export(session: AsyncSession, admin: AdminUser, ip: str | None) -> None:
    await AuditRepository(session).add(
        admin_id=admin.id, action=AuditAction.EXPORT, entity_type="enquiry", ip_address=ip
    )
    await session.commit()


def _line(row: list[object]) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow([csv_safe(v) for v in row])
    return buf.getvalue()


async def stream_csv(settings: Settings) -> AsyncIterator[str]:
    # Own session: the request's session is closed by the time the body streams.
    yield "﻿"  # BOM so Excel opens the file as UTF-8 (₹, Hindi names)
    yield _line(COLUMNS)
    async with SessionLocal() as session:
        async for e, latest_note in EnquiryRepository(session).stream_for_export():
            # Phone numbers written as ="…" would be formulas; plain text keeps the "+".
            yield _line(
                [
                    enquiry_reference(e.id),
                    f"{e.created_at.astimezone(settings.tz):%d-%m-%Y %H:%M}",
                    e.name,
                    e.company,
                    e.phone,
                    e.email,
                    e.location,
                    e.project_type,
                    e.system_size,
                    STATUS_LABELS[e.status],
                    f"{e.follow_up_date:%d-%m-%Y}" if e.follow_up_date else "",
                    enquiry_reference(e.duplicate_of) if e.duplicate_of else "",
                    e.message,
                    latest_note,
                ]
            )
