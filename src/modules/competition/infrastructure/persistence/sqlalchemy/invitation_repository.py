"""Invitation Repository - SQLAlchemy Implementation."""

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.invitation_repository_interface import (
    InvitationRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitacion_pendiente import (
    InvitacionPendiente,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    invitations_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _suya_y_aceptable(user_id: UserId, email: str | None, now: datetime) -> ColumnElement[bool]:
    """
    Las que aún puede aceptar: PENDING y sin caducar en `now`, a su usuario o al
    correo al que se mandó antes de su alta (sin mayúsculas ni espacios).
    """
    tabla = invitations_table.c
    para_quien = tabla.invitee_user_id == user_id
    if email and email.strip():
        para_quien = or_(para_quien, tabla.invitee_email == email.strip().lower())
    return and_(para_quien, tabla.status == InvitationStatus.PENDING, tabla.expires_at > now)


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

    async def find_by_id_for_update(self, invitation_id: InvitationId) -> Invitation | None:
        # `populate_existing`: sin el, SQLAlchemy devuelve el objeto que la sesion
        # ya tenia, con el estado de antes del bloqueo (mismo patron que las
        # competiciones, BE #375)
        stmt = (
            select(Invitation)
            .where(Invitation._id == invitation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        conditions = [Invitation._competition_id == competition_id]
        if status is not None:
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
        if status is not None:
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
        if status is not None:
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

    async def find_acceptable_ids(
        self, invitation_ids: list[InvitationId], now: datetime
    ) -> set[InvitationId]:
        """Solo el id: sin cargar las invitaciones."""
        if not invitation_ids:
            return set()
        tabla = invitations_table.c
        stmt = select(tabla.id).where(
            tabla.id.in_(invitation_ids),
            tabla.status == InvitationStatus.PENDING,
            tabla.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def competiciones_con_invitacion_pendiente(
        self, user_id: UserId, email: str | None, now: datetime
    ) -> set[CompetitionId]:
        """Solo el id de la competición: sin cargar las invitaciones."""
        stmt = select(invitations_table.c.competition_id).where(
            _suya_y_aceptable(user_id, email, now)
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def pendiente_de(
        self, user_id: UserId, email: str | None, competition_id: CompetitionId, now: datetime
    ) -> InvitacionPendiente | None:
        """Su invitación aún aceptable a esa competición, la más reciente: solo id y caducidad."""
        tabla = invitations_table.c
        stmt = (
            select(tabla.id, tabla.expires_at)
            .where(_suya_y_aceptable(user_id, email, now), tabla.competition_id == competition_id)
            .order_by(tabla.created_at.desc())
            .limit(1)
        )
        fila = (await self._session.execute(stmt)).first()
        # El decorador de la columna ya da un InvitationId
        return InvitacionPendiente(fila.id, fila.expires_at) if fila else None

    async def find_pending_by_competition(self, competition_id: CompetitionId) -> list[Invitation]:
        stmt = select(Invitation).where(
            and_(
                Invitation._competition_id == competition_id,
                Invitation._status == InvitationStatus.PENDING,
            )
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
        if status is not None:
            conditions.append(Invitation._status == status)
        if since is not None:
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
        # Identity conditions use OR (email OR user_id match the same person)
        identity_conditions = []
        if email is not None:
            identity_conditions.append(Invitation._invitee_email == email.strip().lower())
        if user_id is not None:
            identity_conditions.append(Invitation._invitee_user_id == user_id)

        if not identity_conditions:
            return 0

        where_clauses = [or_(*identity_conditions)]
        if status is not None:
            where_clauses.append(Invitation._status == status)

        stmt = select(func.count()).select_from(Invitation).where(and_(*where_clauses))
        result = await self._session.execute(stmt)
        return result.scalar() or 0
