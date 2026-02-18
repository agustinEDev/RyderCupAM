"""Invitation Repository - SQLAlchemy Implementation."""

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.invitation_repository_interface import (
    InvitationRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyInvitationRepository(InvitationRepositoryInterface):
    """Implementacion asincrona del repositorio de invitaciones con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, invitation: Invitation) -> None:
        self._session.add(invitation)

    async def update(self, invitation: Invitation) -> None:
        self._session.add(invitation)

    async def find_by_id(self, invitation_id: InvitationId) -> Invitation | None:
        return await self._session.get(Invitation, invitation_id)

    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        conditions = [Invitation._competition_id == competition_id]
        if status:
            conditions.append(Invitation._status == status)

        stmt = (
            select(Invitation)
            .where(and_(*conditions))
            .order_by(Invitation._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_invitee_email(
        self,
        email: str,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        conditions = [Invitation._invitee_email == email.strip().lower()]
        if status:
            conditions.append(Invitation._status == status)

        stmt = (
            select(Invitation)
            .where(and_(*conditions))
            .order_by(Invitation._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_invitee_user_id(
        self,
        user_id: UserId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        conditions = [Invitation._invitee_user_id == user_id]
        if status:
            conditions.append(Invitation._status == status)

        stmt = (
            select(Invitation)
            .where(and_(*conditions))
            .order_by(Invitation._created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_pending_by_email_and_competition(
        self, email: str, competition_id: CompetitionId
    ) -> Invitation | None:
        stmt = select(Invitation).where(
            and_(
                Invitation._invitee_email == email.strip().lower(),
                Invitation._competition_id == competition_id,
                Invitation._status == InvitationStatus.PENDING,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def count_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        since: datetime | None = None,
    ) -> int:
        conditions = [Invitation._competition_id == competition_id]
        if status:
            conditions.append(Invitation._status == status)
        if since:
            conditions.append(Invitation._created_at >= since)

        stmt = select(func.count()).select_from(Invitation).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def count_by_invitee(
        self,
        email: str | None = None,
        user_id: UserId | None = None,
        status: InvitationStatus | None = None,
    ) -> int:
        conditions = []
        if email:
            conditions.append(Invitation._invitee_email == email.strip().lower())
        if user_id:
            conditions.append(Invitation._invitee_user_id == user_id)
        if status:
            conditions.append(Invitation._status == status)

        if not conditions:
            return 0

        stmt = select(func.count()).select_from(Invitation).where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.scalar() or 0
