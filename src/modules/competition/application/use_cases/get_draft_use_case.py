"""
Caso de Uso: Mirar la sala de draft (FE #653).

La ceremonia la ve todo el mundo en directo desde la ficha de la competicion,
y mirarla es ademas lo que mueve el reloj: el turno agotado lo resuelve quien
mire, como la anotacion se abre sola al llegar el primer golpe (BE #305). No
hay ningun proceso de fondo contando minutos.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from src.modules.competition.application.dto.draft_dto import DraftStateDTO
from src.modules.competition.application.services.draft_room import DraftRoom
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetDraftUseCase:
    """Caso de uso para consultar la sala de draft de una competicion."""

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

    async def execute(self, competition_id: UUID, user_id: UserId) -> DraftStateDTO | None:
        """
        Devuelve la sala al dia, resolviendo los minutos que se hayan agotado.

        Args:
            competition_id: La competicion
            user_id: Quien mira. Tiene que ser de esta competicion: la sala la
                ve el grupo, pero el grupo es el de ESA competicion

        Returns:
            La sala, o None si todavia no se ha lanzado el sorteo

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionParticipantError: Si quien mira no es de esta
                competicion
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)
            # Sin bloquear: mirar es leer, y la sala la refrescan doce móviles
            # cada pocos segundos
            competition = await self._room.competicion(comp_id, bloquear=False)
            await self._room.comprobar_que_es_de_la_competicion(competition, user_id)
            draft = await self._uow.drafts.find_by_competition(comp_id)
            if draft is None:
                return None

            if draft.turn_expired(self._room.ahora):
                # Resolverlo SÍ es escribir, y dos miradas a la vez elegirían
                # dos veces por el mismo turno: se relee todo con la fila
                # bloqueada antes de tocar nada
                competition = await self._room.competicion(comp_id)
                draft = await self._uow.drafts.find_by_competition_for_update(comp_id)
                elegibles = await self._room.elegibles(competition)
                await self._room.al_dia(competition, draft, elegibles)
            else:
                elegibles = await self._room.elegibles(competition)
            return await self._room.estado(competition, draft, elegibles)
