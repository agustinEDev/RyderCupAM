"""
Caso de Uso: Lanzar el sorteo y abrir la sala de draft (FE #653).

Lo lanza el organizador, decidido el 22 sep: es quien decide todo lo demas, y
es lo que hace que la ceremonia empiece cuando la gente ya esta delante. Aunque
falte un capitan por entrar se empieza igual —la aplicacion elegira por el cada
vez que se le agote el minuto— porque esperar a alguien que no aparece deja al
resto mirando una pantalla parada.
"""

import secrets
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from src.modules.competition.application.dto.draft_dto import DraftStateDTO
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.draft_room import DraftRoom
from src.modules.competition.domain.entities.competition import CaptainMissingError
from src.modules.competition.domain.entities.draft import EQUIPOS, Draft
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class DraftAlreadyStartedError(Exception):
    """La sala ya arranco, o los equipos ya estan hechos."""

    pass


class StartDraftUseCase:
    """Caso de uso para lanzar el sorteo de la sala de draft."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        clock: Callable[[], datetime] | None = None,
        sorteo: Callable[[], str] | None = None,
    ):
        """
        Args:
            uow: Unit of Work del modulo
            user_repository: De donde salen nombres y handicaps
            clock: El reloj del servidor, inyectable para los tests
            sorteo: Quien sale primero. `secrets` y no `random` porque decide
                quien elige antes, y se inyecta para poder afirmar en un test
                que sale lo que sale el sorteo y no un equipo fijo
        """
        self._uow = uow
        self._room = DraftRoom(uow, user_repository, clock)
        self._sorteo = sorteo or (lambda: secrets.choice(EQUIPOS))

    async def execute(
        self, competition_id: UUID, user_id: UserId, is_admin: bool = False
    ) -> DraftStateDTO:
        """
        Sortea quien empieza y arranca su turno.

        Args:
            competition_id: La competicion
            user_id: Quien lanza el sorteo
            is_admin: Si es administrador

        Returns:
            La sala recien abierta

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionCreatorError: Si no es el creador ni admin
            CompetitionNotClosedError: Si las inscripciones siguen abiertas
            CaptainMissingError: Si falta algun capitan, o no hay ninguno
            DraftAlreadyStartedError: Si la sala ya arranco o hay equipos
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)
            competition = await self._room.competicion(comp_id)
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el organizador lanza el sorteo")
            if competition.status != CompetitionStatus.CLOSED:
                # Con las inscripciones abiertas la plantilla todavia puede
                # crecer, y el draft habria sido sobre otra lista
                raise CompetitionNotClosedError(
                    f"La competición debe estar en estado CLOSED. "
                    f"Estado actual: {competition.status.value}"
                )
            # El draft ES los capitanes eligiendo: sin los dos no hay quien elija.
            # `captains_for_team_split` avisa si falta uno; si no hay ninguno, la
            # sala no tiene sentido
            capitanes = competition.captains_for_team_split()
            if capitanes is None:
                raise CaptainMissingError(
                    "Nombra a los dos capitanes antes de abrir la sala de draft"
                )

            if await self._uow.team_assignments.find_by_competition(comp_id) is not None:
                # Un draft sobre equipos ya hechos los reharia por detras
                raise DraftAlreadyStartedError(
                    "Los equipos de esta competición ya están repartidos"
                )
            draft = await self._uow.drafts.find_by_competition_for_update(comp_id)
            if draft is not None:
                # Volver a sortear a mitad cambiaria el orden con elecciones hechas
                raise DraftAlreadyStartedError("La sala de draft ya estaba abierta")

            capitan_a, capitan_b = capitanes
            draft = Draft.create(
                competition_id=comp_id,
                team_a_captain_id=capitan_a,
                team_b_captain_id=capitan_b,
            )
            # El sorteo, delante de los dos, y una sola vez
            draft.start(first_pick=self._sorteo(), ahora=self._room.ahora)
            await self._uow.drafts.add(draft)

            elegibles = await self._room.elegibles(competition)
            return await self._room.estado(competition, draft, elegibles)
