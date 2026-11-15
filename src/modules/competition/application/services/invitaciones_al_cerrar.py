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

from src.modules.competition.application.services.inscripcion_que_vuelve import viva
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus


async def sin_plaza_para_las_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Invitation]:
    """Rechaza por falta de plazas las pendientes y las que esperan (llena estando
    cerrada, 15 nov 2026); las pendientes ya caducadas, caducadas.

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
    return cerradas + await sin_plaza_para_las_que_esperan(uow, competition_id)


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


@dataclass(frozen=True)
class AlReabrir:
    """Lo que pasa al reabrir con las que esperaban: vuelven, o se quedan sin plaza."""

    vuelven: tuple[Invitation, ...] = ()
    sin_plaza: tuple[Invitation, ...] = ()


async def al_reabrir(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    *,
    libres: int | None,
    sin_sitio: bool,
) -> AlReabrir:
    """Al reabrir, las que esperaban, de la más antigua a la más nueva (P2, O1, C1, C2).

    - Quien ya está inscrito por otro camino: se retira la suya, sin aviso (C2).
    - Con partidos ya generados (`sin_sitio`), o sin plazas `libres` para ella: sin
      plaza (O1, C1). Con `libres` None no hay tope (franjas).
    - Las demás vuelven a pendientes, con 7 días nuevos (P2).

    Dentro de la transacción de quien llama, que avisa ya guardado.
    """
    vuelven: list[Invitation] = []
    sin_plaza: list[Invitation] = []
    esperan = await uow.invitations.find_by_competition_and_status_for_update(
        competition_id, InvitationStatus.ON_HOLD
    )
    for invitacion in sorted(esperan, key=lambda i: i.created_at):
        if invitacion.invitee_user_id is not None and viva(
            await uow.enrollments.find_by_user_and_competition(
                invitacion.invitee_user_id, competition_id
            )
        ):
            invitacion.cancel()
        elif sin_sitio or (libres is not None and len(vuelven) >= libres):
            invitacion.reject_for_no_room()
            sin_plaza.append(invitacion)
        else:
            invitacion.resume()
            vuelven.append(invitacion)
        await uow.invitations.update(invitacion)
    return AlReabrir(vuelven=tuple(vuelven), sin_plaza=tuple(sin_plaza))


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
