from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClickEvent


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: ClickEvent) -> None:
        self.session.add(event)
        await self.session.flush()
