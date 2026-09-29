import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, admin_id: uuid.UUID) -> AdminUser | None:
        return await self.session.get(AdminUser, admin_id)

    async def get_by_email(self, email: str) -> AdminUser | None:
        stmt = select(AdminUser).where(AdminUser.email == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, admin: AdminUser) -> AdminUser:
        self.session.add(admin)
        await self.session.flush()
        return admin
