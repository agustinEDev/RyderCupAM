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

    # La que deja programada el organizador: una por competición (#251)

    @abstractmethod
    async def programar(
        self, competition_id: CompetitionId, para: datetime, momento: datetime
    ) -> None:
        """Programa la actualización de esa competición; sustituye a la anterior."""

    @abstractmethod
    async def programada_de(self, competition_id: CompetitionId) -> datetime | None:
        """Para cuándo está programada, si lo está."""

    @abstractmethod
    async def anular_programada(self, competition_id: CompetitionId) -> None:
        """Quita la programada de esa competición, si la hay."""

    @abstractmethod
    async def programadas_vencidas(self, ahora: datetime) -> list[CompetitionId]:
        """Las competiciones cuya programada ya ha llegado a su hora."""

    @abstractmethod
    async def en_curso_sin_actividad_desde(
        self, limite: datetime
    ) -> list[ActualizacionDeHandicaps]:
        """
        Las que siguen en curso sin haber apuntado nada desde `limite` (ni empezado
        después): las que se quedaron a medias porque el servidor se reinició.
        """
