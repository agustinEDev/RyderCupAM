"""Las actualizaciones de hándicaps, en memoria (tests)."""

import uuid
from dataclasses import replace
from datetime import datetime

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
)
from src.modules.competition.domain.repositories.handicap_update_repository_interface import (
    HandicapUpdateRepositoryInterface,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryHandicapUpdateRepository(HandicapUpdateRepositoryInterface):
    def __init__(self):
        # Copias, como una base de datos: lo que no se guarda no cambia
        self._actualizaciones: dict[uuid.UUID, ActualizacionDeHandicaps] = {}
        self._resultados: dict[tuple[uuid.UUID, UserId], Intento] = {}
        self._cuando: dict[tuple[uuid.UUID, UserId], datetime] = {}
        self._programadas: dict[CompetitionId, datetime] = {}

    async def add(self, actualizacion: ActualizacionDeHandicaps) -> None:
        self._actualizaciones[actualizacion.id] = replace(actualizacion)

    async def update(self, actualizacion: ActualizacionDeHandicaps) -> None:
        self._actualizaciones[actualizacion.id] = replace(actualizacion)

    async def find_by_id(self, update_id: uuid.UUID) -> ActualizacionDeHandicaps | None:
        guardada = self._actualizaciones.get(update_id)
        return None if guardada is None else replace(guardada)

    async def ultima_de(self, competition_id: CompetitionId) -> ActualizacionDeHandicaps | None:
        # La última que se guardó: en los tests el reloj puede ser el mismo
        suyas = [a for a in self._actualizaciones.values() if a.competition_id == competition_id]
        return replace(suyas[-1]) if suyas else None

    async def resultados(self, update_id: uuid.UUID) -> dict[UserId, Intento]:
        return {
            user_id: intento
            for (actualizacion, user_id), intento in self._resultados.items()
            if actualizacion == update_id
        }

    async def apuntar(
        self,
        update_id: uuid.UUID,
        user_id: UserId,
        resultado: ResultadoRefresco,
        momento: datetime,
    ) -> None:
        self._cuando[(update_id, user_id)] = momento
        anterior = self._resultados.get((update_id, user_id))
        self._resultados[(update_id, user_id)] = Intento(
            resultado, 1 if anterior is None else anterior.intentos + 1
        )

    async def programar(
        self, competition_id: CompetitionId, para: datetime, momento: datetime
    ) -> None:
        self._programadas[competition_id] = para

    async def programada_de(self, competition_id: CompetitionId) -> datetime | None:
        return self._programadas.get(competition_id)

    async def anular_programada(self, competition_id: CompetitionId) -> None:
        self._programadas.pop(competition_id, None)

    async def programadas_vencidas(self, ahora: datetime) -> list[CompetitionId]:
        return [c for c, para in self._programadas.items() if para <= ahora]

    async def en_curso_sin_actividad_desde(
        self, limite: datetime
    ) -> list[ActualizacionDeHandicaps]:
        def ultima_actividad(a: ActualizacionDeHandicaps) -> datetime:
            suyas = [m for (u, _), m in self._cuando.items() if u == a.id]
            return max([a.creada, *([a.reanudada] if a.reanudada else []), *suyas])

        return [
            replace(a)
            for a in self._actualizaciones.values()
            if a.sigue() and ultima_actividad(a) < limite
        ]
