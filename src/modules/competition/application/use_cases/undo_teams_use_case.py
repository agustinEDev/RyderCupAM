"""Caso de Uso: deshacer los equipos a mano (decidido el 30 oct 2026)."""

from uuid import UUID

from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class NoTeamsError(Exception):
    """No hay equipos formados que deshacer."""

    error_code = "NO_TEAMS"
    # El texto del 409: fijo, nunca el de la excepción (CodeQL)
    MENSAJE = "There are no teams to undo."


class TeamsLockedError(Exception):
    """Con partidos generados, o ya empezada, los equipos son lo jugado."""

    error_code = "TEAMS_LOCKED"
    MENSAJE = "Matches already exist: the teams can no longer be undone."


class UndoTeamsUseCase:
    """
    El organizador deshace los equipos para que pueda entrar alguien nuevo.

    Con los equipos formados no se invita ni se vuelven a formar (TEAMS_FORMED).
    Es el mismo reinicio que al quitar a un jugador: fuera equipos, sala de
    draft, sobres y subcapitanes; los capitanes se quedan y se repite el draft.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, competition_id: UUID, user_id: UserId, is_admin: bool = False) -> None:
        """
        Deshace los equipos de la competición.

        Args:
            competition_id: La competición
            user_id: Quien lo pide
            is_admin: Si es administrador (no hace falta organizar)

        Raises:
            CompetitionNotFoundError: Si no existe
            NotCompetitionCreatorError: Si no la organiza ni es admin
            NoTeamsError: Si no tiene equipos formados
            TeamsLockedError: Si ya hay partidos o ha empezado
        """
        async with self._uow:
            # Con la fila bloqueada, como al formarlos y al quitar a alguien
            competition = await self._uow.competitions.find_by_id_for_update(
                CompetitionId(competition_id)
            )
            if not competition:
                raise CompetitionNotFoundError(f"No existe competición con ID {competition_id}")
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede deshacer los equipos")
            if await self._uow.team_assignments.find_by_competition(competition.id) is None:
                raise NoTeamsError("No hay equipos formados")
            if not await TeamAssignmentWriter.deshacer(self._uow, competition):
                raise TeamsLockedError("Ya hay partidos: los equipos no se pueden deshacer")
