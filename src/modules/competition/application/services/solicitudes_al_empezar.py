"""
Al empezar la competición, las solicitudes que nadie atendió se rechazan (21 oct).

Hasta que se juega, el organizador puede aprobarlas: en una Ryder, incluso con la
inscripción cerrada. Una vez en juego ya no caben, y si siguieran pendientes al
organizador le seguirían saliendo «Aprobar» y «Rechazar».

La competición empieza por tres caminos —iniciarla a mano y el primer golpe de
una partida o de un partido—, y los tres llaman a esta regla.
"""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus


async def rechazar_las_solicitudes_pendientes(
    uow: CompetitionUnitOfWorkInterface, competition_id: CompetitionId
) -> None:
    """Rechaza las solicitudes pendientes de la competición.

    Sin aviso, como las invitaciones sin plaza. Las demás inscripciones, intactas.
    """
    for solicitud in await uow.enrollments.find_by_competition_and_status(
        competition_id, EnrollmentStatus.REQUESTED
    ):
        solicitud.reject()
        await uow.enrollments.update(solicitud)
