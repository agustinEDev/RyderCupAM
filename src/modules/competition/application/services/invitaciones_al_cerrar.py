"""
Al empezar la competición, o al llenarse, las invitaciones pendientes se quedan
sin plaza (B-02, BE #359).

Del 24 sep (#710) al 15 nov 2026 era al cerrar la inscripción. Desde B-02 el
organizador solo invita, y una pendiente se acepta hasta que la competición
empieza: la llaman los cuatro caminos de empezar (`solicitudes_al_empezar`).
"""

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


async def sin_plaza_para_las_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Rechaza por falta de plazas las pendientes; las ya caducadas, caducadas.

    Una que caducó sin que nadie la pasara a EXPIRED no se quedó sin plaza: se
    quedó sin respuesta, y así debe constar.

    Devuelve las que ha cerrado: quien llama, ya guardado, retira su aviso de
    invitado en Actividad (Agustín, 22 oct 2026).
    """
    cerradas = []
    # Con sus filas bloqueadas: un DECLINE a la vez no se pisa con NO_ROOM (revisión)
    for invitacion in await uow.invitations.find_pending_by_competition_for_update(competition_id):
        invitacion.check_expiration()
        if invitacion.is_pending():
            invitacion.reject_for_no_room()
        await uow.invitations.update(invitacion)
        cerradas.append(invitacion)
    return cerradas


async def al_ocupar_una_plaza(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    aprobadas_antes: int,
    max_players: int,
) -> list[Invitation]:
    """Si esa plaza era la última, las pendientes se quedan sin plaza ya (BE #359).

    Quien llega tarde se entera en el momento, no al aceptar. Una sola regla para
    todos los caminos que ocupan una plaza —aceptar una invitación, aprobar una
    solicitud—: con una copia en cada uno, aprobar se
    quedó sin ella. La carrera entre dos que ocupan a la vez la resuelve la fila
    bloqueada de la competición: entra el primero.
    """
    if aprobadas_antes + 1 >= max_players:
        return await sin_plaza_para_las_pendientes(uow, competition_id)
    return []
