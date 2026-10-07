"""
Repositorio: las actualizaciones de hándicaps de cada competición (#251).

Cada actualización con su estado, y lo que contestó la RFEG por cada jugador:
el último resultado y cuántas veces se preguntó. Sirve para no preguntar dos
veces lo mismo, para terminar solo lo que falta si una quedó a medias, y para
decir al organizador quién se quedó sin actualizar.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class HandicapUpdateRepositoryInterface(ABC):
    """Las actualizaciones de hándicaps y sus resultados por jugador."""

    @abstractmethod
    async def add(self, actualizacion: ActualizacionDeHandicaps) -> None:
        """Guarda una actualización nueva."""

    @abstractmethod
    async def update(self, actualizacion: ActualizacionDeHandicaps) -> None:
        """Guarda el estado de una actualización."""

    @abstractmethod
    async def find_by_id(self, update_id: uuid.UUID) -> ActualizacionDeHandicaps | None:
        """Una actualización por su id."""

    @abstractmethod
    async def ultima_de(self, competition_id: CompetitionId) -> ActualizacionDeHandicaps | None:
        """La más reciente de una competición, si hay alguna."""

    @abstractmethod
    async def resultados(self, update_id: uuid.UUID) -> dict[UserId, Intento]:
        """Lo que contestó la RFEG por cada jugador en esa actualización."""

    @abstractmethod
    async def apuntar(
        self,
        update_id: uuid.UUID,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        """Apunta el resultado de un jugador; si ya tenía, lo sustituye y suma un intento."""
