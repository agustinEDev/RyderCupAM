"""
Los cambios de barras por campo en memoria: lo mismo que promete la interfaz.

| Caso                                               | Resultado                         |
|----------------------------------------------------|-----------------------------------|
| Sin cambios                                         | Vacíos                            |
| Propio y del campo para un género                   | Salen en `del_campo`              |
| Fijar otra vez                                      | Pisa el anterior (único por clave) |
| Quitar (None)                                       | Desaparece                        |
| Otro campo u otra competición                       | No se mezclan                     |
| Quitar el campo de la competición                   | Se van todos los de ese campo     |
| Un cambio propio de una inscripción retirada        | No sale (como en Postgres)        |
"""

from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_barras_por_campo_repository import (
    InMemoryBarrasPorCampoRepository,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_enrollment_repository import (
    InMemoryEnrollmentRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


async def _repo_e_inscripcion(competicion, estado=EnrollmentStatus.APPROVED):
    """El repositorio, con el de inscripciones de la unidad de trabajo, y una inscripción."""
    inscripciones = InMemoryEnrollmentRepository()
    inscripcion = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competicion,
        user_id=UserId(uuid4()),
        status=estado,
    )
    await inscripciones.add(inscripcion)
    return InMemoryBarrasPorCampoRepository(inscripciones), inscripcion


async def test_barras_por_campo_guardan_quitan_y_no_se_mezclan():
    """
    Given dos competiciones con dos campos
    When se fijan, se pisan y se quitan cambios
    Then cada campo devuelve solo los suyos, el último gana y quitar los borra
    """
    comp, otra = CompetitionId(uuid4()), CompetitionId(uuid4())
    campo, otro_campo = GolfCourseId(uuid4()), GolfCourseId(uuid4())
    repo, ana = await _repo_e_inscripcion(comp)

    assert (await repo.del_campo(comp, campo)).propias == {}

    await repo.fijar_propia(ana, campo, TeeColor.BLUE)
    await repo.fijar_propia(ana, campo, TeeColor.RED)
    await repo.fijar_del_campo(comp, campo, Gender.FEMALE, TeeColor.RED)
    await repo.fijar_del_campo(otra, campo, Gender.MALE, TeeColor.WHITE)
    await repo.fijar_propia(ana, otro_campo, TeeColor.WHITE)

    cambios = await repo.del_campo(comp, campo)
    assert cambios.propias == {ana.user_id: TeeColor.RED}
    assert cambios.por_genero == {Gender.FEMALE: TeeColor.RED}

    await repo.fijar_propia(ana, campo, None)
    await repo.fijar_del_campo(comp, campo, Gender.FEMALE, None)
    vacio = await repo.del_campo(comp, campo)
    assert (vacio.propias, vacio.por_genero) == ({}, {})
    assert (await repo.del_campo(otra, campo)).por_genero == {Gender.MALE: TeeColor.WHITE}


async def test_barras_por_campo_se_van_con_el_campo_quitado():
    """
    Given cambios en dos campos de una competición
    When se quita uno de la competición
    Then se van los suyos y los del otro siguen
    """
    comp = CompetitionId(uuid4())
    campo, otro_campo = GolfCourseId(uuid4()), GolfCourseId(uuid4())
    repo, ana = await _repo_e_inscripcion(comp)
    await repo.fijar_propia(ana, campo, TeeColor.RED)
    await repo.fijar_del_campo(comp, campo, Gender.MALE, TeeColor.WHITE)
    await repo.fijar_propia(ana, otro_campo, TeeColor.BLUE)

    await repo.borrar_del_campo(comp, campo)

    quitado = await repo.del_campo(comp, campo)
    assert (quitado.propias, quitado.por_genero) == ({}, {})
    assert (await repo.del_campo(comp, otro_campo)).propias == {ana.user_id: TeeColor.BLUE}


async def test_barras_por_campo_no_devuelven_las_propias_de_una_inscripcion_retirada():
    """
    Given una inscripción retirada que tenía un cambio propio en un campo
    When se piden los cambios de ese campo
    Then su cambio propio no sale: solo cuentan los de inscripciones aprobadas
    """
    comp, campo = CompetitionId(uuid4()), GolfCourseId(uuid4())
    repo, retirada = await _repo_e_inscripcion(comp, EnrollmentStatus.WITHDRAWN)
    await repo.fijar_propia(retirada, campo, TeeColor.BLUE)

    assert (await repo.del_campo(comp, campo)).propias == {}
