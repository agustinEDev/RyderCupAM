"""
Volver a entrar no recupera los cambios propios de barras por campo (20 nov 2026).

Decisión conservadora: quien se fue y vuelve no debe encontrarse unas barras por
campo que nadie le ve fijar. Al reutilizar su inscripción cerrada se borran sus
cambios propios (R1); la barra del campo para su género (R2) es de la competición
y se queda.
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.services.inscripcion_que_vuelve import (
    guardar_la_inscripcion,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


async def test_volver_a_entrar_borra_sus_cambios_propios_por_campo():
    """
    Given una inscripción retirada con un cambio propio a azules en un campo, y rojas
        fijadas en ese campo para las mujeres
    When vuelve a entrar con esa misma inscripción
    Then su cambio propio ya no está; la barra del campo para las mujeres, sí
    """
    uow = InMemoryUnitOfWork()
    competicion, campo = CompetitionId(uuid4()), GolfCourseId(uuid4())
    vieja = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competicion,
        user_id=UserId(uuid4()),
        status=EnrollmentStatus.WITHDRAWN,
    )
    await uow.enrollments.add(vieja)
    await uow.barras_por_campo.fijar_propia(vieja, campo, TeeColor.BLUE)
    await uow.barras_por_campo.fijar_del_campo(competicion, campo, Gender.FEMALE, TeeColor.RED)

    await guardar_la_inscripcion(
        uow, vieja, aprobada=True, competition_id=competicion, user_id=vieja.user_id
    )

    cambios = await uow.barras_por_campo.del_campo(competicion, campo)
    assert cambios.propias == {}
    assert cambios.por_genero == {Gender.FEMALE: TeeColor.RED}
