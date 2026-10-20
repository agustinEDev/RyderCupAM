"""Historial de aceptaciones de los Términos con SQLAlchemy (async)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.repositories.terms_acceptance_repository_interface import (
    TermsAcceptanceRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.terms_acceptance_mapper import (
    terms_acceptances_table,
)


class SQLAlchemyTermsAcceptanceRepository(TermsAcceptanceRepositoryInterface):
    """Inserta y lee filas de terms_acceptances en la sesión del UoW."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, acceptance: TermsAcceptance) -> None:
        self._session.add(acceptance)

    async def find_by_user_id(self, user_id: UserId) -> list[TermsAcceptance]:
        statement = (
            select(TermsAcceptance)
            .where(terms_acceptances_table.c.user_id == user_id)
            .order_by(terms_acceptances_table.c.accepted_at)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
