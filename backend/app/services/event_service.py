from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClickEvent
from app.repositories.event_repo import EventRepository
from app.schemas.event import ClickEventIn


async def record_click(session: AsyncSession, data: ClickEventIn) -> None:
    await EventRepository(session).add(
        ClickEvent(type=data.type, page=data.page, utm_source=data.utm_source)
    )
    await session.commit()
