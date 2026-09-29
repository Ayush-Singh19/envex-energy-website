from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Enquiry


class EnquiryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
