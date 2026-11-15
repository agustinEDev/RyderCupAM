"""
Con los equipos formados, quedan así (decidido el 29 oct 2026).

Salgan del draft o los forme el organizador, el jugador ya no sale por su
cuenta, y los equipos no se vuelven a formar. Si alguien no puede jugar, el
organizador le quita y todo se reinicia (`TeamAssignmentWriter.deshacer`).

Entrar, sí (B3, 15 nov 2026): sin partidos, el organizador invita, y al aceptar
el invitado (o al aprobarle una solicitud) los equipos se deshacen. Con la sala
de draft abierta, no se invita ni se acepta, hasta que acabe.
"""

from src.modules.competition.application.services.baja_de_la_competicion import (
    exigir_sin_draft_abierto,
)
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


async def exigir_que_se_pueda_invitar(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> None:
    """
    Antes de invitar (B3, 15 nov 2026): la invitación tiene que poder aceptarse.

    Con la sala de draft abierta, no (hasta que acabe). Con los equipos formados,
    solo si aún se pueden deshacer —sin partidos—: al aceptarla, se deshacen.

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition: La competición

    Raises:
        DraftInProgressError: Con la sala de draft abierta
        TeamsFormedError: Con los equipos formados y partidos
    """
    await exigir_sin_draft_abierto(uow, competition.id)
    if await TeamAssignmentWriter.deshacible(uow, competition) is None:
        await exigir_sin_equipos_formados(uow, competition.id)


async def reiniciar_para_que_entre(
    uow: CompetitionUnitOfWorkInterface, competition: Competition
) -> bool:
    """
    Antes de que entre alguien (aceptando una invitación, B3, o aprobado): nadie
    entra durante el draft (Agustín, 15 nov 2026), y los equipos se reinician.

    Con partidos el reinicio no se hace, y quien entrara se quedaba fuera de
    los dos equipos sin forma de arreglarlo (decidido el 30 oct 2026).

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition: La competición

    Returns:
        Si se deshicieron (para avisar al organizador, B3)

    Raises:
        DraftInProgressError: Con la sala de draft abierta
        TeamsFormedError: Si tiene equipos y no se pueden reiniciar
    """
    await exigir_sin_draft_abierto(uow, competition.id)
    if await TeamAssignmentWriter.deshacer(uow, competition):
        return True
    await exigir_sin_equipos_formados(uow, competition.id)
    return False
