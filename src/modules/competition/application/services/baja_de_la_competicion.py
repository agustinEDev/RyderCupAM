"""
Sacar a un jugador de una competición (release social 2, 27 oct 2026).

Lo mismo tanto si se retira él como si le quita el organizador: sale de sus
partidas sin salir, suelta sus plazas en las franjas (que pasan a quien espera),
si era capitán sube su subcapitán y, si estaba en un equipo formado sin
partidos, los equipos se deshacen (descompensados, uno se quedaba sin jugar).
"""

from datetime import UTC, datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
    esta_jugada,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    sacar_de_sus_partidas,
)
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)


async def sacar_de_la_competicion(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition | None,
    enrollment: Enrollment,
    *,
    zonas: ICompetitionTimezone | None,
    ahora: datetime,
) -> dict:
    """
    Le saca de todo lo de la competición. La inscripción ya está retirada.

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition: La competición (None si no se encontró)
        enrollment: Su inscripción
        zonas: Para saber qué partidas ya salieron por su hora (#251)
        ahora: El momento de la baja

    Returns:
        Las salidas de antes y después de cada ronda tocada, para avisar
    """
    # Sale de sus partidas sin salir, también ya iniciada (D2, #251)
    fotos = await sacar_de_sus_partidas(
        uow, enrollment.competition_id, enrollment.user_id, zonas=zonas, ahora=ahora
    )

    # Y suelta sus plazas en las franjas de un stroke play, si aún no se juega:
    # empezada, son las del historial de lo jugado (#251)
    if competition is not None and competition.status.allows_tee_window_edits():
        # Las de franjas ya jugadas (tras volver atrás) se quedan: historial
        sesiones = {
            r.id: r for r in await uow.rounds.find_by_competition(enrollment.competition_id)
        }
        suyas = []
        for plaza in await uow.plazas.de_la_competicion(enrollment.competition_id):
            if plaza.user_id != enrollment.user_id:
                continue
            franja = sesiones.get(plaza.round_id)
            if franja is not None and not esta_jugada(franja):
                await uow.plazas.quitar(plaza.round_id, plaza.user_id)
                suyas.append(plaza.round_id)
        # Fuera de las listas, y sus plazas para los que esperan
        esperas = EsperasDeLaCompeticion(uow)
        await esperas.sacar_de_todas(competition, enrollment.user_id)
        await esperas.rellenar_varias(competition, suyas, datetime.now(UTC))

    if competition is None:
        return fotos

    # Si era capitan, su puesto queda libre (o lo ocupa su subcapitan)
    if competition.handle_withdrawal(enrollment.user_id):
        await uow.competitions.update(competition)

    # En un equipo formado sin partidos, los equipos se deshacen (decidido el
    # 27 oct 2026): descompensados, al generar uno se quedaba sin jugar
    reparto = await uow.team_assignments.find_by_competition(competition.id)
    if reparto is not None and reparto.get_player_team(enrollment.user_id) is not None:
        await TeamAssignmentWriter.deshacer(uow, competition)

    return fotos
