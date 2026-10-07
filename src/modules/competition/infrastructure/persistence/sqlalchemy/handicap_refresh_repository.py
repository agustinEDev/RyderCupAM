"""Los resultados del refresco de las 3:00, en Postgres (BE #502)."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.competition.domain.repositories.handicap_refresh_repository_interface import (
    HandicapRefreshRepositoryInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    handicap_refreshes_table,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyHandicapRefreshRepository(HandicapRefreshRepositoryInterface):
    """Una fila por torneo, día y jugador; un reintento sustituye la anterior."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def del_dia(
        self, competition_id: CompetitionId, dia: date
    ) -> dict[UserId, ResultadoRefresco]:
        tabla = handicap_refreshes_table
        result = await self._session.execute(
            select(tabla.c.user_id, tabla.c.result).where(
                tabla.c.competition_id == competition_id, tabla.c.play_date == dia
            )
        )
        return {fila.user_id: ResultadoRefresco(fila.result) for fila in result}

    async def apuntar(
        self,
        competition_id: CompetitionId,
        dia: date,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        tabla = handicap_refreshes_table
        fila = insert(tabla).values(
            competition_id=competition_id,
            play_date=dia,
            user_id=user_id,
            result=str(resultado),
            refreshed_at=momento,
        )
        await self._session.execute(
            fila.on_conflict_do_update(
                index_elements=[tabla.c.competition_id, tabla.c.play_date, tabla.c.user_id],
                set_={"result": fila.excluded.result, "refreshed_at": fila.excluded.refreshed_at},
            )
        )
