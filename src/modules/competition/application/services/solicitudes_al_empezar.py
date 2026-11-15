"""
Al empezar la competición, lo pendiente se cierra: las solicitudes que nadie
atendió se rechazan (21 oct) y las invitaciones que esperaban a que se reabriera
la inscripción se quedan sin plaza (P3, 15 nov 2026).

Hasta que se juega, el organizador puede aprobarlas: en una Ryder, incluso con la
inscripción cerrada. Una vez en juego ya no caben, y si siguieran pendientes al
organizador le seguirían saliendo «Aprobar» y «Rechazar». Las invitaciones, desde
el 15 nov, al cerrar esperan (antes se quedaban sin plaza, #710): si se reabre,
vuelven; si empieza sin reabrir, se quedan sin plaza.

La competición empieza por cuatro caminos —iniciarla a mano, el primer golpe de
una partida o de un partido, y el primer hoyo que corrige el organizador en una
partida—, y los cuatro llaman a `cerrar_lo_pendiente`.
"""

from dataclasses import dataclass

from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    sin_plaza_para_las_que_esperan,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus


async def rechazar_las_solicitudes_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> list[Enrollment]:
    """Rechaza las solicitudes pendientes de la competición y las devuelve.

    Sin correo, como las invitaciones sin plaza. Las demás inscripciones,
    intactas. Quien la llama avisa en Actividad («se cerró sin plaza», BE-2)
    con las que devuelve, ya guardado: aquí se está dentro de su transacción.
    """
    rechazadas = []
    for solicitud in await uow.enrollments.find_by_competition_and_status(
        competition_id, EnrollmentStatus.REQUESTED
    ):
        solicitud.reject()
        await uow.enrollments.update(solicitud)
        rechazadas.append(solicitud)
    return rechazadas


@dataclass(frozen=True)
class CerradoAlEmpezar:
    """Lo que se cerró al empezar: solicitudes rechazadas e invitaciones sin plaza (P3)."""

    solicitudes: tuple[Enrollment, ...] = ()
    invitaciones: tuple[Invitation, ...] = ()


async def cerrar_lo_pendiente(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> CerradoAlEmpezar:
    """Rechaza las solicitudes pendientes y deja sin plaza las invitaciones en espera
    (las ya caducadas, caducadas). Dentro de la transacción de quien llama, que avisa
    con `avisar_de_lo_cerrado` ya guardado."""
    return CerradoAlEmpezar(
        solicitudes=tuple(await rechazar_las_solicitudes_pendientes(uow, competition_id)),
        invitaciones=tuple(await sin_plaza_para_las_que_esperan(uow, competition_id)),
    )


async def avisar_de_lo_cerrado(
    actividad: AvisosDeActividad, competition: Competition, cerrado: CerradoAlEmpezar
) -> None:
    """Ya guardado: «tu solicitud se cerró sin plaza» (BE-2), y a cada invitado
    que esperaba, «no hubo plaza» (P3). Su aviso de invitado se retiró al cerrar."""
    await actividad.requests_closed(competition, cerrado.solicitudes)
    await actividad.invitations_no_place(competition, cerrado.invitaciones)
