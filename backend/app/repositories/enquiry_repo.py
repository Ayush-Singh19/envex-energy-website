import re
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import CLOSED_STATUSES, EnquiryStatus
from app.models import ClickEvent, Enquiry, EnquiryNote

_NON_DIGITS = re.compile(r"\D")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True, slots=True)
class EnquiryFilters:
    status: EnquiryStatus | None = None  # None = every status except not_relevant
    q: str | None = None
    project_type: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None  # exclusive


class EnquiryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- public submission ----------------------------------------------------------

    async def find_latest_by_phone_since(self, phone: str, since: datetime) -> Enquiry | None:
        """Most recent enquiry from this phone created at or after ``since``.

        Served by the (phone, created_at DESC) index.
        """
        stmt = (
            select(Enquiry)
            .where(Enquiry.phone == phone, Enquiry.created_at >= since)
            .order_by(Enquiry.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, enquiry: Enquiry) -> Enquiry:
        self.session.add(enquiry)
        await self.session.flush()
        return enquiry

    # ---- admin list ---------------------------------------------------------------------

    @staticmethod
    def _where(filters: EnquiryFilters) -> list[ColumnElement[bool]]:
        conds: list[ColumnElement[bool]] = []
        if filters.status is None:
            conds.append(Enquiry.status != EnquiryStatus.NOT_RELEVANT)
        else:
            conds.append(Enquiry.status == filters.status)
        if filters.project_type:
            conds.append(Enquiry.project_type == filters.project_type)
        if filters.created_from:
            conds.append(Enquiry.created_at >= filters.created_from)
        if filters.created_to:
            conds.append(Enquiry.created_at < filters.created_to)
        if filters.q:
            like = f"%{_escape_like(filters.q)}%"
            text_match = [
                Enquiry.name.ilike(like, escape="\\"),
                Enquiry.email.ilike(like, escape="\\"),
                Enquiry.location.ilike(like, escape="\\"),
                Enquiry.company.ilike(like, escape="\\"),
            ]
            digits = _NON_DIGITS.sub("", filters.q)
            if len(digits) >= 3:  # "43210" finds +919876543210
                text_match.append(Enquiry.phone.like(f"%{digits}%"))
            conds.append(or_(*text_match))
        return conds

    async def list(
        self, filters: EnquiryFilters, *, offset: int, limit: int
    ) -> tuple[Sequence[Enquiry], int]:
        where = self._where(filters)
        total = (
            await self.session.execute(select(func.count()).select_from(Enquiry).where(*where))
        ).scalar_one()
        stmt = (
            select(Enquiry)
            .where(*where)
            .order_by(Enquiry.created_at.desc(), Enquiry.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all(), total

    async def count_by_status(self) -> dict[EnquiryStatus, int]:
        stmt = select(Enquiry.status, func.count()).group_by(Enquiry.status)
        return {status: n for status, n in (await self.session.execute(stmt)).all()}

    # ---- admin detail -------------------------------------------------------------------

    async def get(self, enquiry_id: uuid.UUID, *, with_notes: bool = False) -> Enquiry | None:
        stmt: Select[tuple[Enquiry]] = select(Enquiry).where(Enquiry.id == enquiry_id)
        if with_notes:
            stmt = stmt.options(selectinload(Enquiry.notes).joinedload(EnquiryNote.admin))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_repeat_of(self, enquiry_id: uuid.UUID) -> Enquiry | None:
        stmt = (
            select(Enquiry)
            .where(Enquiry.duplicate_of == enquiry_id)
            .order_by(Enquiry.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_note(self, note: EnquiryNote) -> EnquiryNote:
        self.session.add(note)
        await self.session.flush()
        return note

    # ---- today screen -------------------------------------------------------------------

    async def count(self, *conds: ColumnElement[bool]) -> int:
        stmt = select(func.count()).select_from(Enquiry).where(*conds)
        return (await self.session.execute(stmt)).scalar_one()

    async def waiting_for_call(self, limit: int) -> Sequence[Enquiry]:
        stmt = (
            select(Enquiry)
            .where(Enquiry.status == EnquiryStatus.NEW)
            .order_by(Enquiry.created_at.asc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def follow_ups_due(self, today: date, limit: int) -> Sequence[Enquiry]:
        stmt = (
            select(Enquiry)
            .where(
                Enquiry.follow_up_date.is_not(None),
                Enquiry.follow_up_date <= today,
                Enquiry.status.not_in(CLOSED_STATUSES),
            )
            .order_by(Enquiry.follow_up_date.asc(), Enquiry.created_at.asc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def follow_ups_between(self, start: date, end: date) -> int:
        return await self.count(
            and_(Enquiry.follow_up_date >= start, Enquiry.follow_up_date <= end),
            Enquiry.status.not_in(CLOSED_STATUSES),
        )

    async def click_counts_since(self, since: datetime) -> dict[str, int]:
        stmt = (
            select(ClickEvent.type, func.count())
            .where(ClickEvent.created_at >= since)
            .group_by(ClickEvent.type)
        )
        return {str(t): n for t, n in (await self.session.execute(stmt)).all()}

    # ---- export -------------------------------------------------------------------------

    async def stream_for_export(self) -> AsyncIterator[tuple[Enquiry, str | None]]:
        """Every enquiry, newest first, with its latest note. Streamed in batches."""
        latest_note = (
            select(EnquiryNote.note)
            .where(EnquiryNote.enquiry_id == Enquiry.id)
            .order_by(EnquiryNote.created_at.desc())
            .limit(1)
            .correlate(Enquiry)
            .scalar_subquery()
        )
        stmt = (
            select(Enquiry, latest_note)
            .order_by(Enquiry.created_at.desc())
            .execution_options(yield_per=500)
        )
        result = await self.session.stream(stmt)
        async for enquiry, note in result:
            yield enquiry, note
