"""
Sacar a un jugador de una competición (release social 2, 27 oct 2026).

Lo mismo tanto si se retira él como si le quita el organizador: sale de sus
partidas sin salir, suelta sus plazas en las franjas (que pasan a quien espera),
si era capitán sube su subcapitán y, si estaba en un equipo formado sin
partidos, sale de su equipo y los demás se quedan (release social 3, 28 oct
2026; antes se deshacían los equipos).
"""

from datetime import datetime

from src.modules.competition.application.ports.competition_timezone import ICompetitionTimezone
from src.modules.competition.application.services import equipos_que_cambian
from src.modules.competition.application.services.esperas_de_la_competicion import (
    EsperasDeLaCompeticion,
    esta_jugada,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    sacar_de_sus_partidas,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.user.domain.value_objects.user_id import UserId

DRAFT_IN_PROGRESS = "DRAFT_IN_PROGRESS"


class DraftInProgressError(Exception):
    """Con la sala de draft abierta nadie sale: la sala no se enteraria (27 oct 2026)."""

    error_code = DRAFT_IN_PROGRESS


async def exigir_sin_draft_abierto(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> None:
    """
    Nadie sale de la competicion con la sala de draft abierta (decidido el 27 oct
    2026): la sala seguiria con sus elecciones y sus capitanes de antes, y podia
    acabar con un retirado en un equipo. Es un rato corto: se espera a que acabe.

    Args:
        uow: Unit of Work ya abierto
        competition_id: La competicion

    Raises:
        DraftInProgressError: Si hay una sala sin terminar (esperando el sorteo o eligiendo)
    """
    sala = await uow.drafts.find_by_competition(competition_id)
    if sala is not None and sala.status != DraftStatus.COMPLETED:
        raise DraftInProgressError("Espera a que termine el draft")


async def sacar_de_la_competicion(
    uow: CompetitionUnitOfWorkInterface,
    competition: Competition | None,
    enrollment: Enrollment,
    *,
    zonas: ICompetitionTimezone | None,
    ahora: datetime,
    asignadas: list[tuple[Round, UserId]] | None = None,
    capitanes_a_avisar: list[UserId] | None = None,
) -> dict:
    """
    Le saca de todo lo de la competición. La inscripción ya está retirada.

    Args:
        uow: Unit of Work ya abierto, con la competición bloqueada
        competition: La competición (None si no se encontró)
        enrollment: Su inscripción
        zonas: Para saber qué partidas ya salieron por su hora (#251)
        ahora: El momento de la baja
        asignadas: Si se da, ahí quedan las plazas que la lista dio por su baja,
            para avisar tras guardar (A3, 28 oct 2026)
        capitanes_a_avisar: Si se da, ahí quedan los capitanes a los que avisar
            de que sus equipos cambiaron (T4, 28 oct 2026)

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
        await esperas.rellenar_varias(competition, suyas, ahora)
        if asignadas is not None:
            asignadas.extend(esperas.asignadas)

    if competition is None:
        return fotos

    # Si era capitan, su puesto queda libre (o lo ocupa su subcapitan)
    if competition.handle_withdrawal(enrollment.user_id):
        await uow.competitions.update(competition)

    # Sale de su equipo y los demás se quedan; sus sobres, a borrador (T2, T4:
    # 28 oct 2026, cambia el deshacer del 27 oct)
    capitanes = await equipos_que_cambian.al_salir(uow, competition, enrollment.user_id)
    if capitanes_a_avisar is not None:
        capitanes_a_avisar.extend(capitanes)

    return fotos
