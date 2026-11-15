"""
Entrar en una competición con una inscripción vieja (release social 2, 27 oct 2026).

Las tres vías de entrar —aceptar una invitación, pedir plaza y la inscripción a
mano del organizador— miraban si había CUALQUIER fila suya, y la restricción
única (competición, usuario) no mira el estado. Quien tenía una rechazada,
cancelada o retirada no podía volver. Aquí, la misma regla para las tres: una
viva (aprobada o pendiente) sigue impidiéndolo; una cerrada se reutiliza.
"""

from decimal import Decimal

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId


def viva(inscripcion: Enrollment | None) -> Enrollment | None:
    """
    La inscripción que impide volver a entrar: aprobada o pendiente.

    Args:
        inscripcion: La que tiene en la competición, si tiene alguna

    Returns:
        Esa misma si sigue viva; None si no hay o está cerrada
    """
    if inscripcion is None or inscripcion.status.is_final():
        return None
    return inscripcion


async def guardar_la_inscripcion(
    uow: CompetitionUnitOfWorkInterface,
    vieja: Enrollment | None,
    *,
    aprobada: bool,
    competition_id: CompetitionId,
    user_id: UserId,
    tee_color: TeeColor | None = None,
    custom_handicap: Decimal | None = None,
) -> Enrollment:
    """
    Le inscribe: con su fila cerrada si la tiene, o con una nueva.

    Quien llama ya ha comprobado que no tiene una viva (`viva`).

    Args:
        uow: La unidad de trabajo de la petición
        vieja: Su inscripción cerrada, si tiene una
        aprobada: Entra ya, o pide plaza
        competition_id: Dónde entra
        user_id: Quién entra
        tee_color: Su barra, si la elige
        custom_handicap: El hándicap que le pone el organizador, si lo hay

    Returns:
        La inscripción guardada
    """
    if vieja is not None:
        vieja.volver_a_entrar(
            aprobada=aprobada, tee_color=tee_color, custom_handicap=custom_handicap
        )
        await uow.enrollments.update(vieja)
        return vieja

    if aprobada:
        nueva = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition_id,
            user_id=user_id,
            custom_handicap=custom_handicap,
            tee_color=tee_color,
        )
    else:
        nueva = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=competition_id,
            user_id=user_id,
            tee_color=tee_color,
        )
    await uow.enrollments.add(nueva)
    return nueva
