"""
`PUT /enrollments/{id}/tee` (BE #912): lo que no se puede llega con su código y
un texto fijo, para que la pantalla lo diga en su idioma; y la ruta pasa al caso
de uso quién lo pide y si es admin.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    EnrollmentNotApprovedError,
    PendingGameNotRecalculableError,
    TeeChangeClosedError,
    TeeNotAvailableError,
    TeeNotOnPendingCourseError,
    TeeRemovalLeavesNoValidTeeError,
)
from src.modules.competition.infrastructure.api.v1 import enrollment_routes
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.application.dto.user_dto import UserResponseDTO


def _quien(is_admin=False) -> UserResponseDTO:
    return UserResponseDTO.model_construct(id=uuid4(), email="j@test.com", is_admin=is_admin)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "codigo", "estado"),
    [
        (TeeNotAvailableError, "TEE_NOT_AVAILABLE", 422),
        (TeeNotOnPendingCourseError, "TEE_NOT_ON_PENDING_COURSE", 422),
        (TeeChangeClosedError, "TEE_CHANGE_CLOSED", 409),
        (EnrollmentNotApprovedError, "ENROLLMENT_NOT_APPROVED", 409),
        (PendingGameNotRecalculableError, "PENDING_GAME_NOT_RECALCULABLE", 409),
    ],
)
async def test_change_tee_refused_answers_its_code_and_a_fixed_text(error, codigo, estado):
    """
    Given un caso de uso que no deja cambiar las barras
    When llega la petición
    Then la respuesta lleva su código HTTP, su error_code y un texto fijo, no el
        de la excepción
    """
    caso = AsyncMock()
    caso.execute.side_effect = error("texto interno con datos")

    respuesta = await enrollment_routes.change_enrollment_tee(
        uuid4(), enrollment_routes.ChangeTeeBody(tee_color=TeeColor.RED), _quien(), caso
    )

    assert respuesta.status_code == estado
    cuerpo = json.loads(respuesta.body)
    assert cuerpo["error_code"] == codigo
    assert "texto interno" not in cuerpo["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("is_admin", [False, True])
async def test_change_tee_passes_who_asks_and_the_tee(is_admin):
    """
    Given una petición para cambiar a rojas (o volver a las de por defecto)
    When llega a la ruta
    Then el caso de uso recibe la inscripción, las barras, quién lo pide y si es admin
    """
    caso = AsyncMock()
    quien = _quien(is_admin)
    inscripcion = uuid4()

    await enrollment_routes.change_enrollment_tee(
        inscripcion, enrollment_routes.ChangeTeeBody(tee_color=None), quien, caso
    )

    peticion, usuario = caso.execute.call_args.args
    assert peticion.enrollment_id == inscripcion
    assert peticion.tee_color is None
    assert str(usuario.value) == str(quien.id)
    assert caso.execute.call_args.kwargs == {"is_admin": is_admin}


def test_change_tee_body_rejects_an_unknown_colour():
    """
    Given un color que no es de las barras
    When se valida el cuerpo
    Then no pasa (422 de FastAPI)
    """
    with pytest.raises(ValueError):
        enrollment_routes.ChangeTeeBody(tee_color="PURPLE")


@pytest.mark.asyncio
async def test_change_tee_not_on_a_pending_course_answers_its_own_text():
    """
    Given un caso de uso que rechaza la general porque no vale en un campo con algo
        pendiente
    When llega la petición
    Then 422 TEE_NOT_ON_PENDING_COURSE con su texto: que antes fije la de ese campo
    """
    caso = AsyncMock()
    caso.execute.side_effect = TeeNotOnPendingCourseError("texto interno")

    respuesta = await enrollment_routes.change_enrollment_tee(
        uuid4(), enrollment_routes.ChangeTeeBody(tee_color=TeeColor.RED), _quien(), caso
    )

    assert json.loads(respuesta.body) == {
        "detail": "That tee is not available on a course with games still to play; "
        "set that course's tee first.",
        "error_code": "TEE_NOT_ON_PENDING_COURSE",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "texto"),
    [
        (
            TeeNotAvailableError,
            "That tee is not available for this player on a course with games still to play.",
        ),
        (
            TeeRemovalLeavesNoValidTeeError,
            "Removing it would leave a game still to play without a valid tee on this course.",
        ),
    ],
)
async def test_change_tee_not_available_answers_its_text_without_rated(error, texto):
    """
    Given un caso de uso que rechaza con TEE_NOT_AVAILABLE (en general, o al quitar
        una barra fijada)
    When llega la petición
    Then 422 TEE_NOT_AVAILABLE con su texto, que no habla de valoración (en
        SCRATCH no hace falta)
    """
    caso = AsyncMock()
    caso.execute.side_effect = error("texto interno")

    respuesta = await enrollment_routes.change_enrollment_tee(
        uuid4(), enrollment_routes.ChangeTeeBody(tee_color=TeeColor.RED), _quien(), caso
    )

    assert respuesta.status_code == 422
    assert json.loads(respuesta.body) == {"detail": texto, "error_code": "TEE_NOT_AVAILABLE"}
