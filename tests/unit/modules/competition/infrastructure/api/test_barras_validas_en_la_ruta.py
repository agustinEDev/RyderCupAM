"""
`GET /enrollments/{id}/tees` (BE #912): lo que no se puede llega con su código y un
texto fijo, y la ruta pasa al caso de uso quién lo pide y si es admin.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import EnrollmentTeesResponseDTO
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
)
from src.modules.competition.infrastructure.api.v1 import enrollment_routes
from src.modules.user.application.dto.user_dto import UserResponseDTO


def _quien(is_admin=False) -> UserResponseDTO:
    return UserResponseDTO.model_construct(id=uuid4(), email="j@test.com", is_admin=is_admin)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "codigo"),
    [
        (TeeChangeClosedError, "TEE_CHANGE_CLOSED"),
        (EnrollmentNotApprovedError, "ENROLLMENT_NOT_APPROVED"),
    ],
)
async def test_get_tees_refused_answers_409_with_its_code_and_a_fixed_text(error, codigo):
    """
    Given un caso de uso que no deja ver las barras
    When llega la petición
    Then 409 con su error_code y un texto fijo, no el de la excepción
    """
    caso = AsyncMock()
    caso.execute.side_effect = error("texto interno con datos")

    respuesta = await enrollment_routes.get_enrollment_tees(uuid4(), _quien(), caso)

    assert respuesta.status_code == 409
    cuerpo = json.loads(respuesta.body)
    assert cuerpo["error_code"] == codigo
    assert "texto interno" not in cuerpo["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("is_admin", [False, True])
async def test_get_tees_passes_who_asks_and_returns_the_tees(is_admin):
    """
    Given un caso de uso que responde rojas y azules
    When llega la petición
    Then recibe la inscripción, quién lo pide y si es admin, y la respuesta es la suya
    """
    caso = AsyncMock()
    caso.execute.return_value = EnrollmentTeesResponseDTO(
        tees=["RED", "BLUE"], default_tee="RED", current_tee=None
    )
    quien = _quien(is_admin)
    inscripcion = uuid4()

    respuesta = await enrollment_routes.get_enrollment_tees(inscripcion, quien, caso)

    inscripcion_pedida, usuario = caso.execute.call_args.args
    assert inscripcion_pedida == inscripcion
    assert str(usuario.value) == str(quien.id)
    assert caso.execute.call_args.kwargs == {"is_admin": is_admin}
    assert respuesta.tees == ["RED", "BLUE"]
