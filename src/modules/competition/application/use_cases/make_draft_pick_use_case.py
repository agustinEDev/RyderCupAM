"""
Caso de Uso: Elegir a un jugador en la sala de draft (FE #653).

Elige el capitan del equipo de turno, y nadie mas. Antes de nada se resuelven
los minutos agotados: el capitan que se duerme no puede elegir por encima de lo
que ya eligio la aplicacion por el.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from src.modules.competition.application.dto.draft_dto import DraftStateDTO
from src.modules.competition.application.services.draft_room import DraftRoom
from src.modules.competition.domain.entities.draft import DraftNotRunningError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class MakeDraftPickUseCase:
    """Caso de uso para que un capitan elija a un jugador."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        clock: Callable[[], datetime] | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde salen nombres y handicaps
            clock: El reloj del servidor, inyectable para los tests
        """
        self._uow = uow
        self._room = DraftRoom(uow, user_repository, clock)

    async def execute(
        self, competition_id: UUID, user_id: UserId, player_id: UUID
    ) -> DraftStateDTO:
        """
        Elige a `player_id` para el equipo de `user_id`.

        Args:
            competition_id: La competicion
            user_id: El capitan que elige
            player_id: A quien elige

        Returns:
            La sala despues de la eleccion

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            DraftNotRunningError: Si la sala no esta en marcha
            NotYourTurnError: Si no le toca a ese capitan
            PlayerAlreadyPickedError: Si ese jugador ya no se puede elegir
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)
            competition = await self._room.competicion(comp_id)
            # Bloqueada: dos capitanes pueden pulsar a la vez, y sin bloqueo los
            # dos leerian el mismo turno y elegirian los dos
            draft = await self._uow.drafts.find_by_competition_for_update(comp_id)
            if draft is None:
                raise DraftNotRunningError("Todavía no se ha lanzado el sorteo")

            elegibles = await self._room.elegibles(competition)
            # Antes de comprobar el turno: si se agoto el minuto, ya no es suyo
            await self._room.al_dia(competition, draft, elegibles)

            draft.check_turn(user_id)
            draft.pick(UserId(player_id), elegibles, self._room.ahora)
            await self._room.guardar(competition, draft)

            return await self._room.estado(competition, draft, elegibles)
