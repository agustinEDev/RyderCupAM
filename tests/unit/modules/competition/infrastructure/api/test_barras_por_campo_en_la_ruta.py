"""
Las rutas de las barras por campo (20 nov 2026): lo que no se puede llega con su
código y un texto fijo, y pasan al caso de uso quién lo pide y si es admin.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    CourseNotInCompetitionError,
    PendingGameNotRecalculableError,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.infrastructure.api.v1 import (
    competition_golf_course_routes,
    enrollment_routes,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.shared.domain.value_objects.gender import Gender

NEGATIVAS = [
    (TeeNotAvailableError, "TEE_NOT_AVAILABLE", 422),
    (TeeChangeClosedError, "TEE_CHANGE_CLOSED", 409),
    (PendingGameNotRecalculableError, "PENDING_GAME_NOT_RECALCULABLE", 409),
    (EnrollmentNotApprovedError, "ENROLLMENT_NOT_APPROVED", 409),
    (CourseNotInCompetitionError, "COURSE_NOT_IN_COMPETITION", 404),
]


def _quien(is_admin=False) -> UserResponseDTO:
    return UserResponseDTO.model_construct(id=uuid4(), email="o@test.com", is_admin=is_admin)


async def _propia(caso, quien=None, color=TeeColor.BLUE):
    return await enrollment_routes.change_enrollment_course_tee(
        uuid4(),
        uuid4(),
        enrollment_routes.ChangeCourseTeeBody(tee_color=color),
        quien or _quien(),
        caso,
    )


async def _del_campo(caso, quien=None, color=TeeColor.BLUE):
    return await competition_golf_course_routes.set_competition_course_tee(
        uuid4(),
        uuid4(),
        competition_golf_course_routes.SetCourseTeeBody(gender=Gender.FEMALE, tee_color=color),
        quien or _quien(),
        caso,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", [_propia, _del_campo])
@pytest.mark.parametrize(("error", "codigo", "estado"), NEGATIVAS)
async def test_course_tee_refused_answers_its_code_and_a_fixed_text(ruta, error, codigo, estado):
    """
    Given un caso de uso que no deja fijar la barra
    When llega la petición a cualquiera de las dos rutas
    Then su código HTTP, su error_code y un texto fijo, no el de la excepción
    """
    caso = AsyncMock()
    caso.execute.side_effect = error("texto interno con datos")

    respuesta = await ruta(caso)

    assert respuesta.status_code == estado
    cuerpo = json.loads(respuesta.body)
    assert cuerpo["error_code"] == codigo
    assert "texto interno" not in cuerpo["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("is_admin", [False, True])
async def test_enrollment_course_tee_passes_the_ids_the_tee_and_who_asks(is_admin):
    """
    Given una petición para fijar azules en un campo
    When llega a la ruta de la inscripción
    Then el caso de uso recibe inscripción, campo, barra, quién y si es admin
    """
    caso = AsyncMock()
    quien = _quien(is_admin)
    inscripcion, campo = uuid4(), uuid4()

    await enrollment_routes.change_enrollment_course_tee(
        inscripcion, campo, enrollment_routes.ChangeCourseTeeBody(tee_color=None), quien, caso
    )

    peticion, usuario = caso.execute.call_args.args
    assert (peticion.enrollment_id, peticion.golf_course_id, peticion.tee_color) == (
        inscripcion,
        campo,
        None,
    )
    assert str(usuario.value) == str(quien.id)
    assert caso.execute.call_args.kwargs == {"is_admin": is_admin}


@pytest.mark.asyncio
async def test_competition_course_tee_passes_the_gender_and_the_tee():
    """
    Given una petición para fijar azules a las mujeres en un campo
    When llega a la ruta de la competición
    Then el caso de uso recibe competición, campo, género y barra
    """
    caso = AsyncMock()
    competicion, campo = uuid4(), uuid4()

    await competition_golf_course_routes.set_competition_course_tee(
        competicion,
        campo,
        competition_golf_course_routes.SetCourseTeeBody(
            gender=Gender.FEMALE, tee_color=TeeColor.BLUE
        ),
        _quien(),
        caso,
    )

    peticion = caso.execute.call_args.args[0]
    assert (peticion.competition_id, peticion.golf_course_id) == (competicion, campo)
    assert (peticion.gender, peticion.tee_color) == (Gender.FEMALE, TeeColor.BLUE)


def test_competition_course_tee_body_rejects_an_unknown_gender():
    """
    Given un género que no es MALE ni FEMALE
    When se valida el cuerpo
    Then no pasa (422 de FastAPI)
    """
    with pytest.raises(ValueError):
        competition_golf_course_routes.SetCourseTeeBody(gender="OTHER", tee_color=None)
