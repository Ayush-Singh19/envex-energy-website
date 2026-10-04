import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditAction
from app.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        admin_id: uuid.UUID | None,
        action: AuditAction,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                admin_id=admin_id,
                action=action.value,
                entity_type=entity_type,
                entity_id=entity_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
            )
        )
        await self.session.flush()

    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars())
