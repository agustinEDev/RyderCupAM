"""Round Repository - SQLAlchemy Implementation."""

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.round_repository_interface import (
    RoundRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.shared.infrastructure.persistence.leidos_en_la_sesion import (
    lista_leida,
    olvidar_listas,
    recordar_lista,
)

# Las rondas de cada competición ya leídas en la petición
_RONDAS = "rondas_de"


class SQLAlchemyRoundRepository(RoundRepositoryInterface):
    """Implementacion asincrona del repositorio de rondas con SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, round: Round) -> None:
        """Añade la ronda y olvida las listas de rondas recordadas en la petición."""
        self._session.add(round)
        olvidar_listas(self._session, _RONDAS)

    async def update(self, round: Round) -> None:
        """Guarda la ronda y olvida las listas recordadas: su fecha puede haber cambiado."""
        self._session.add(round)
        # Cambiar la fecha la reordena entre las de su competición
        olvidar_listas(self._session, _RONDAS)

    async def find_by_id(self, round_id: RoundId) -> Round | None:
        return await self._session.get(Round, round_id)

    async def find_by_id_for_update(self, round_id: RoundId) -> Round | None:
        # `populate_existing`: si la sesion ya la tenia en memoria, se pisa con
        # lo que hay en la base de datos. Sin eso, tras esperar el bloqueo se
        # seguiria decidiendo con el estado de antes
        statement = (
            select(Round)
            .where(Round._id == round_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_competition(self, competition_id: CompetitionId) -> list[Round]:
        # Una vez por petición: la ficha las pedía para «tus jornadas» y para
        # saber si se puede borrar (PR 2 de rendimiento)
        """Las rondas de la competición por fecha; una sola lectura por petición."""
        if (ya := lista_leida(self._session, (_RONDAS, competition_id))) is not None:
            # En el orden de sus fechas de ahora: una pudo cambiar sin `update`
            return sorted(ya, key=lambda r: (r.round_date, r.created_at))
        statement = (
            select(Round)
            .where(Round._competition_id == competition_id)
            .order_by(Round._round_date.asc(), Round._created_at.asc())
        )
        result = await self._session.execute(statement)
        rondas = list(result.scalars().all())
        recordar_lista(self._session, (_RONDAS, competition_id), rondas)
        return rondas

    async def find_by_competition_and_date(
        self, competition_id: CompetitionId, round_date: date
    ) -> list[Round]:
        statement = (
            select(Round)
            .where(
                and_(
                    Round._competition_id == competition_id,
                    Round._round_date == round_date,
                )
            )
            .order_by(Round._created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def delete(self, round_id: RoundId) -> bool:
        """Borra la ronda, si existe, y olvida las listas recordadas."""
        round = await self.find_by_id(round_id)
        if round is None:
            return False
        await self._session.delete(round)
        olvidar_listas(self._session, _RONDAS)
        return True

    async def find_by_ids(self, round_ids: list[RoundId]) -> list[Round]:
        if not round_ids:
            return []
        result = await self._session.execute(select(Round).where(Round._id.in_(round_ids)))
        return list(result.scalars().all())
