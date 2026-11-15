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

from dataclasses import dataclass

from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class AlLlenarse:
    """Las que se cerraron al llenarse: todas (fuera su aviso de invitado) y, de ellas,
    las que esperaban (a esas, «no hubo plaza», como al empezar o cancelar)."""

    cerradas: tuple[Invitation, ...] = ()
    esperaban: tuple[Invitation, ...] = ()


async def avisar_al_llenarse(
    actividad: AvisosDeActividad, competition: Competition, llena: AlLlenarse
) -> None:
    """Ya guardado: fuera los avisos de invitado y, a quien esperaba, «no hubo plaza»."""
    await actividad.invitations_closed(llena.cerradas)
    await actividad.invitations_no_place(competition, llena.esperaban)


async def sin_plaza_para_las_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> AlLlenarse:
    """Rechaza por falta de plazas las pendientes y las que esperan (llena estando
    cerrada, 15 nov 2026); las pendientes ya caducadas, caducadas.

    Una que caducó sin que nadie la pasara a EXPIRED no se quedó sin plaza: se
    quedó sin respuesta, y así debe constar.

    Devuelve las que ha cerrado: quien llama, ya guardado, retira su aviso de
    invitado en Actividad (Agustín, 22 oct 2026) y avisa a quien esperaba.
    """
    cerradas = []
    for invitacion in await uow.invitations.find_pending_by_competition(competition_id):
        invitacion.check_expiration()
        if invitacion.is_pending():
            invitacion.reject_for_no_room()
        await uow.invitations.update(invitacion)
        cerradas.append(invitacion)
    esperaban = await sin_plaza_para_las_que_esperan(uow, competition_id)
    return AlLlenarse(cerradas=tuple(cerradas + esperaban), esperaban=tuple(esperaban))


async def al_ocupar_una_plaza(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    aprobadas_antes: int,
    max_players: int,
) -> AlLlenarse:
    """Si esa plaza era la última, las pendientes se quedan sin plaza ya (BE #359).

    Quien llega tarde se entera en el momento, no al aceptar. Una sola regla para
    todos los caminos que ocupan una plaza —aceptar una invitación, aprobar una
    solicitud, inscribir directamente—: con una copia en cada uno, aprobar se
    quedó sin ella. La carrera entre dos que ocupan a la vez la resuelve la fila
    bloqueada de la competición: entra el primero.
    """
    if aprobadas_antes + 1 >= max_players:
        return await sin_plaza_para_las_pendientes(uow, competition_id)
    return AlLlenarse()


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


@dataclass(frozen=True)
class AlReabrir:
    """Lo que pasa al reabrir con las que esperaban: vuelven, o se quedan sin plaza."""

    vuelven: tuple[Invitation, ...] = ()
    sin_plaza: tuple[Invitation, ...] = ()


async def al_reabrir(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    esperan: list[Invitation],
    *,
    sin_sitio: bool,
) -> AlReabrir:
    """Al reabrir, las que esperaban (P2, O1, C1, C2), ya leídas con sus filas bloqueadas.

    - Quien ya está inscrito (aprobado) por otro camino: se retira la suya, sin aviso
      (C2). Una solicitud sin aprobar no cuenta.
    - Sin sitio (partidos ya generados, o ni una plaza libre): sin plaza (O1, C1).
    - Si no, TODAS vuelven a pendientes, con 7 días nuevos (P2): entra quien antes
      acepte, y al llenarse las demás se quedan sin plaza, como en una abierta (BE #359).

    Dentro de la transacción de quien llama, que avisa ya guardado.
    """
    vuelven: list[Invitation] = []
    sin_plaza: list[Invitation] = []
    for invitacion in esperan:
        if invitacion.invitee_user_id is not None and await _inscrito(
            uow, invitacion.invitee_user_id, competition_id
        ):
            invitacion.cancel()
        elif sin_sitio:
            invitacion.reject_for_no_room()
            sin_plaza.append(invitacion)
        else:
            invitacion.resume()
            vuelven.append(invitacion)
        await uow.invitations.update(invitacion)
    return AlReabrir(vuelven=tuple(vuelven), sin_plaza=tuple(sin_plaza))


async def _inscrito(
    uow: CompetitionUnitOfWorkInterface, user_id: UserId, competition_id: CompetitionId
) -> bool:
    inscripcion = await uow.enrollments.find_by_user_and_competition(user_id, competition_id)
    return inscripcion is not None and inscripcion.is_approved()


async def sin_plaza_para_las_que_esperan(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Al empezar o cancelarse: las que esperaban se quedan sin plaza (P3).

    Esperando no caducan. Devuelve las que se quedaron sin plaza, para el «no
    hubo plaza» de cada una ya guardado.
    """
    sin_plaza = await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.ON_HOLD
    )
    for invitacion in sin_plaza:
        invitacion.reject_for_no_room()
        await uow.invitations.update(invitacion)
    return sin_plaza


@dataclass(frozen=True)
class CerradasAlCancelar:
    """Lo que cancelar cierra: todas las tocadas (sus avisos de invitado se van) y las
    que se quedaron sin plaza (les llega «no hubo plaza»)."""

    tocadas: tuple[Invitation, ...] = ()
    sin_plaza: tuple[Invitation, ...] = ()


async def al_cancelar(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> CerradasAlCancelar:
    """Al cancelarse: sin plaza las que esperaban y también las pendientes (P3, Agustín,
    15 nov 2026: aunque la inscripción siguiera abierta); las pendientes ya caducadas,
    caducadas."""
    tocadas: list[Invitation] = []
    sin_plaza = await sin_plaza_para_las_que_esperan(uow, competition_id)
    for invitacion in await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.PENDING
    ):
        invitacion.check_expiration()
        if invitacion.is_pending():
            invitacion.reject_for_no_room()
            sin_plaza.append(invitacion)
        await uow.invitations.update(invitacion)
        tocadas.append(invitacion)
    return CerradasAlCancelar(tocadas=tuple(tocadas), sin_plaza=tuple(sin_plaza))
