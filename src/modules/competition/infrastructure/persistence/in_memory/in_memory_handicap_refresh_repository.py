"""Los resultados del refresco de las 3:00, en memoria (tests)."""

from datetime import date, datetime

from src.modules.competition.domain.repositories.handicap_refresh_repository_interface import (
    HandicapRefreshRepositoryInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryHandicapRefreshRepository(HandicapRefreshRepositoryInterface):
    def __init__(self):
        self._filas: dict[tuple[CompetitionId, date, UserId], ResultadoRefresco] = {}

    async def del_dia(
        self, competition_id: CompetitionId, dia: date
    ) -> dict[UserId, ResultadoRefresco]:
        return {
            user_id: resultado
            for (competicion, el_dia, user_id), resultado in self._filas.items()
            if competicion == competition_id and el_dia == dia
        }

    async def apuntar(
        self,
        competition_id: CompetitionId,
        dia: date,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        self._filas[(competition_id, dia, user_id)] = resultado
