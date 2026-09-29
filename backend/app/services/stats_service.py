"""The Today screen: four numbers, who to call, follow-ups due, and website taps."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import EnquiryStatus
from app.models import Enquiry
from app.repositories.enquiry_repo import EnquiryRepository
from app.schemas.stats import ClickCounts, TodayKpis, TodayOut
from app.services.admin_enquiry_service import to_item

CALL_FIRST_LIMIT = 25
FOLLOW_UP_LIMIT = 50


async def today(session: AsyncSession, settings: Settings) -> TodayOut:
    repo = EnquiryRepository(session)
    now = datetime.now(UTC)
    local_now = now.astimezone(settings.tz)
    local_today = local_now.date()
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    kpis = TodayKpis(
        new_this_week=await repo.count(
            Enquiry.created_at >= week_ago, Enquiry.status != EnquiryStatus.NOT_RELEVANT
        ),
        waiting_for_call=await repo.count(Enquiry.status == EnquiryStatus.NEW),
        quotes_out=await repo.count(Enquiry.status == EnquiryStatus.QUOTE_SENT),
        won_this_month=await repo.count(
            Enquiry.status == EnquiryStatus.WON, Enquiry.status_changed_at >= month_start
        ),
        month_label=f"{local_now:%B}",
    )
    clicks = await repo.click_counts_since(week_ago)
    return TodayOut(
        kpis=kpis,
        call_first=[to_item(e, settings) for e in await repo.waiting_for_call(CALL_FIRST_LIMIT)],
        follow_ups=[
            to_item(e, settings) for e in await repo.follow_ups_due(local_today, FOLLOW_UP_LIMIT)
        ],
        later_this_week=await repo.follow_ups_between(
            local_today + timedelta(days=1), local_today + timedelta(days=7)
        ),
        clicks_this_week=ClickCounts(**clicks),
    )
