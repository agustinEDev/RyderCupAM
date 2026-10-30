"""
Con los equipos formados, quedan así (decidido el 29 oct 2026).

Salgan del draft o los forme el organizador, el jugador ya no entra ni sale
por su cuenta, y los equipos no se vuelven a formar. Si alguien no puede
jugar, el organizador le quita y todo se reinicia (`TeamAssignmentWriter.deshacer`).
"""

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
