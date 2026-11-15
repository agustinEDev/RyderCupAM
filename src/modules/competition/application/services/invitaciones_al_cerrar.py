"""
Lo que les pasa a las invitaciones vivas al cerrar, reabrir, empezar o llenarse.

Al llenarse, las pendientes se quedan sin plaza (BE #359). Al cerrar la
inscripción, desde el 15 nov 2026 ya no (antes sí, #710): esperan (ON_HOLD, P1)
y, si el organizador reabre, vuelven a pendientes (P2); si la competición
empieza o se cancela esperando, se quedan sin plaza (P3). La inscripción se
cierra por tres caminos —a mano, por el plazo y al nombrar a los capitanes—, se
reabre por dos —a mano y al mover el torneo (R3)— y empieza por cuatro, así que
cada regla vive aquí una vez.

«En espera» no es la lista de espera de las franjas de un stroke play (`esperas`).
"""

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus


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
    for invitacion in await uow.invitations.find_pending_by_competition(competition_id):
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
    solicitud, inscribir directamente—: con una copia en cada uno, aprobar se
    quedó sin ella. La carrera entre dos que ocupan a la vez la resuelve la fila
    bloqueada de la competición: entra el primero.
    """
    if aprobadas_antes + 1 >= max_players:
        return await sin_plaza_para_las_pendientes(uow, competition_id)
    return []


async def en_espera_las_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Al cerrar la inscripción: las pendientes esperan (P1); las ya caducadas, caducadas.

    Devuelve todas las que ha tocado: ninguna se puede aceptar ya, y quien llama,
    ya guardado, retira su aviso de invitado (como hasta ahora al cerrar).
    """
    tocadas = []
    for invitacion in await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.PENDING
    ):
        invitacion.check_expiration()
        if invitacion.is_pending():
            invitacion.put_on_hold()
        await uow.invitations.update(invitacion)
        tocadas.append(invitacion)
    return tocadas


async def vuelven_las_que_esperan(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Al reabrir: las que esperaban vuelven a pendientes (P2).

    La que caducó mientras esperaba se queda caducada. Devuelve las que vuelven,
    para el «ya puedes aceptar» de cada una cuando quien llama haya guardado.
    """
    vuelven = []
    for invitacion in await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.ON_HOLD
    ):
        invitacion.resume()
        invitacion.check_expiration()
        await uow.invitations.update(invitacion)
        if invitacion.is_pending():
            vuelven.append(invitacion)
    return vuelven


async def sin_plaza_para_las_que_esperan(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Al empezar o cancelarse: las que esperaban se quedan sin plaza (P3).

    La que caducó mientras esperaba se queda caducada. Devuelve las que se
    quedaron sin plaza, para el «no hubo plaza» de cada una ya guardado.
    """
    sin_plaza = []
    for invitacion in await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.ON_HOLD
    ):
        invitacion.check_expiration()
        if invitacion.is_on_hold():
            invitacion.reject_for_no_room()
            sin_plaza.append(invitacion)
        await uow.invitations.update(invitacion)
    return sin_plaza
