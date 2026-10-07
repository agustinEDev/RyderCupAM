"""
Repositorio: lo que pasó al refrescar con la RFEG a cada jugador, un día de juego (BE #502).

Una fila por torneo, día y jugador. Sirve para no preguntar dos veces lo mismo
—el vigilante pasa cada 15 minutos y el servidor puede reiniciarse—, para
reintentar solo lo que falló, y para saber después qué pasó.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class HandicapRefreshRepositoryInterface(ABC):
    """Los resultados del refresco de las 3:00, por torneo y día."""

    @abstractmethod
    async def del_dia(
        self, competition_id: CompetitionId, dia: date
    ) -> dict[UserId, ResultadoRefresco]:
        """El último resultado de cada jugador de ese torneo ese día."""

    @abstractmethod
    async def apuntar(
        self,
        competition_id: CompetitionId,
        dia: date,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        """Apunta (o sustituye, si se reintentó) el resultado de un jugador."""
