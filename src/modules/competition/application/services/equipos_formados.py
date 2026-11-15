"""
Con los equipos formados, quedan así (decidido el 29 oct 2026).

Salgan del draft o los forme el organizador, el jugador ya no entra ni sale
por su cuenta, y los equipos no se vuelven a formar. Si alguien no puede
jugar, el organizador le quita y todo se reinicia (`TeamAssignmentWriter.deshacer`).
"""

from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class TeamsFormedError(Exception):
    """Con los equipos formados, el jugador no entra ni sale y no se rehacen."""

    error_code = "TEAMS_FORMED"
    # El texto del 409: fijo, nunca el de la excepción (CodeQL)
    MENSAJE = "Teams are already formed: ask the organizer."


async def exigir_sin_equipos_formados(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> None:
    """
    Antes de que un jugador entre o salga, o de formar los equipos otra vez.

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition_id: La competición

    Raises:
        TeamsFormedError: Si ya tiene equipos
    """
    if await uow.team_assignments.find_by_competition(competition_id) is not None:
        raise TeamsFormedError("Los equipos ya están formados: habla con el organizador.")


async def reiniciar_para_que_entre(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> None:
    """
    Antes de que el organizador meta a alguien: los equipos se reinician.

    Con partidos el reinicio no se hace, y quien entrara se quedaba fuera de
    los dos equipos sin forma de arreglarlo (decidido el 30 oct 2026).

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition: La competición

    Raises:
        TeamsFormedError: Si tiene equipos y no se pueden reiniciar
    """
    if not await TeamAssignmentWriter.deshacer(uow, competition):
        await exigir_sin_equipos_formados(uow, competition.id)
