"""Data retention, per the security doc.

* Enquiries are deleted 24 months after their last activity (the later of the last
  update and the last note). Their notes go with them.
* Audit-log entries and click events are deleted after 12 months.

Run daily with ``python -m app.scripts.purge_old_data`` (cron, or the host's scheduler).
Each run writes one audit entry with the counts, so the purge itself is on record.
"""

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditAction
from app.models import AuditLog, ClickEvent, Enquiry, EnquiryNote
from app.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PurgeResult:
    enquiries: int
    audit_entries: int
    click_events: int


def _last_activity():
    latest_note = (
        select(func.max(EnquiryNote.created_at))
        .where(EnquiryNote.enquiry_id == Enquiry.id)
        .correlate(Enquiry)
        .scalar_subquery()
    )
    return func.greatest(Enquiry.updated_at, func.coalesce(latest_note, Enquiry.updated_at))


async def purge(
    session: AsyncSession, settings: Settings, *, now: datetime | None = None, dry_run: bool = False
) -> PurgeResult:
    now = now or datetime.now(UTC)
    enquiry_cutoff = now - timedelta(days=settings.retention_enquiry_days)
    log_cutoff = now - timedelta(days=settings.retention_log_days)

    stale = select(Enquiry.id).where(_last_activity() < enquiry_cutoff)
    counts = PurgeResult(
        enquiries=(
            await session.execute(select(func.count()).select_from(stale.subquery()))
        ).scalar_one(),
        audit_entries=(
            await session.execute(
                select(func.count()).select_from(AuditLog).where(AuditLog.created_at < log_cutoff)
            )
        ).scalar_one(),
        click_events=(
            await session.execute(
                select(func.count())
                .select_from(ClickEvent)
                .where(ClickEvent.created_at < log_cutoff)
            )
        ).scalar_one(),
    )
    if dry_run:
        return counts

    # Repeats pointing at a purged enquiry keep their own data; the FK is ON DELETE SET NULL.
    await session.execute(delete(Enquiry).where(Enquiry.id.in_(stale)))
    await session.execute(delete(AuditLog).where(AuditLog.created_at < log_cutoff))
    await session.execute(delete(ClickEvent).where(ClickEvent.created_at < log_cutoff))
    await AuditRepository(session).add(
        admin_id=None,
        action=AuditAction.RETENTION_PURGE,
        entity_type="system",
        new_value=asdict(counts),
    )
    await session.commit()
    logger.info("retention_purge", extra=asdict(counts))
    return counts
