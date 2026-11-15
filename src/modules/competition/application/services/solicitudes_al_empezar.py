"""
Al empezar la competición, lo pendiente se cierra: las solicitudes que nadie
atendió se rechazan (21 oct) y las invitaciones sin responder se quedan sin plaza
(B-02, 15 nov 2026).

Hasta que se juega, el organizador puede aprobarlas: en una Ryder, incluso con la
inscripción cerrada. Una vez en juego ya no caben, y si siguieran pendientes al
organizador le seguirían saliendo «Aprobar» y «Rechazar». Con las invitaciones,
igual: desde el 15 nov cerrar la inscripción ya no las cierra (antes sí, #710), y
se aceptan hasta que empieza.

La competición empieza por cuatro caminos —iniciarla a mano, el primer golpe de
una partida o de un partido, y el primer hoyo que corrige el organizador en una
partida—, y los cuatro llaman a `cerrar_lo_pendiente`.
"""

from dataclasses import dataclass

from src.modules.competition.application.services.avisos_de_actividad import AvisosDeActividad
from src.modules.competition.application.services.invitaciones_al_cerrar import (
    sin_plaza_para_las_pendientes,
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
    """Lo que se cerró al empezar: solicitudes rechazadas e invitaciones sin plaza."""

    solicitudes: tuple[Enrollment, ...] = ()
    invitaciones: tuple[Invitation, ...] = ()


async def cerrar_lo_pendiente(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> CerradoAlEmpezar:
    """Rechaza las solicitudes pendientes y deja sin plaza las invitaciones pendientes
    (las ya caducadas, caducadas). Dentro de la transacción de quien llama, que avisa
    con `avisar_de_lo_cerrado` ya guardado."""
    return CerradoAlEmpezar(
        solicitudes=tuple(await rechazar_las_solicitudes_pendientes(uow, competition_id)),
        invitaciones=tuple(await sin_plaza_para_las_pendientes(uow, competition_id)),
    )


async def avisar_de_lo_cerrado(
    actividad: AvisosDeActividad, competition: Competition, cerrado: CerradoAlEmpezar
) -> None:
    """Ya guardado: «tu solicitud se cerró sin plaza» (BE-2), y cada invitación
    cerrada retira su aviso de invitado (como al llenarse, 22 oct 2026)."""
    await actividad.requests_closed(competition, cerrado.solicitudes)
    await actividad.invitations_closed(cerrado.invitaciones)
