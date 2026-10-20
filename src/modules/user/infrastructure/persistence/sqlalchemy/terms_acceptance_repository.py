"""Historial de aceptaciones de los Términos con SQLAlchemy (async)."""

from datetime import datetime

from sqlalchemy import delete, select
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

    async def has_accepted(self, user_id: UserId, terms_version: str) -> bool:
        statement = (
            select(terms_acceptances_table.c.id)
            .where(terms_acceptances_table.c.user_id == user_id)
            .where(terms_acceptances_table.c.terms_version == terms_version)
            .limit(1)
        )
        return (await self._session.execute(statement)).first() is not None

    async def purge_deleted_before(self, cutoff: datetime) -> int:
        result = await self._session.execute(
            delete(terms_acceptances_table)
            .where(terms_acceptances_table.c.user_deleted_at.is_not(None))
            .where(terms_acceptances_table.c.user_deleted_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)
