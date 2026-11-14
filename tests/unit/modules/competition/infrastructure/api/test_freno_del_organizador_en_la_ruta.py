"""
El tope de invitaciones por organizador llega a la pantalla con su código y su límite
(auditoría de la fase 6, B-03): sin ellos, la app diría un «espera un minuto» genérico.
"""

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.domain.exceptions.competition_violations import (
    InvitationUserRateLimitViolation,
)
from src.modules.competition.infrastructure.api.v1 import invitation_routes
from src.modules.user.application.dto.user_dto import UserResponseDTO

pytestmark = pytest.mark.asyncio


def _organizador() -> UserResponseDTO:
    return UserResponseDTO.model_construct(id=uuid4(), email="org@test.com", is_admin=False)


@pytest.mark.parametrize("por", ["correo", "id"])
async def test_the_organizer_cap_answers_429_with_its_code_and_limit(por):
    caso = AsyncMock()
    caso.execute.side_effect = InvitationUserRateLimitViolation("demasiadas", limit=100)

    if por == "correo":
        respuesta = await invitation_routes.send_invitation_by_email(
            uuid4(),
            invitation_routes.SendInvitationByEmailBody(invitee_email="x@test.com"),
            _organizador(),
            caso,
        )
    else:
        respuesta = await invitation_routes.send_invitation_by_user_id(
            uuid4(),
            invitation_routes.SendInvitationByUserIdBody(invitee_user_id=uuid4()),
            _organizador(),
            caso,
        )

    assert respuesta.status_code == 429
    assert json.loads(respuesta.body) == {
        "detail": "Too many invitations sent in the last hour.",
        "error_code": "INVITATION_USER_RATE_LIMIT",
        "limit": 100,
    }


@pytest.mark.parametrize("por", ["correo", "id"])
async def test_a_per_user_request_brake_survives_deleting_competitions(por, monkeypatch):
    """
    CodeRabbit en BE #845: el tope por filas se pierde si se borra la competición (con sus
    invitaciones). Un freno por usuario que cuenta peticiones, compartido por las dos
    rutas, no: al pasarlo, el mismo 429 y sin llamar al caso de uso.
    """
    from src.config import rate_limit

    contados: list[tuple[str, str, str]] = []

    def no_cabe(limite, ambito, clave):
        contados.append((limite, ambito, clave))
        return False

    monkeypatch.setattr(invitation_routes, "cabe", no_cabe)
    organizador = _organizador()
    caso = AsyncMock()

    if por == "correo":
        respuesta = await invitation_routes.send_invitation_by_email(
            uuid4(),
            invitation_routes.SendInvitationByEmailBody(invitee_email="x@test.com"),
            organizador,
            caso,
        )
    else:
        respuesta = await invitation_routes.send_invitation_by_user_id(
            uuid4(),
            invitation_routes.SendInvitationByUserIdBody(invitee_user_id=uuid4()),
            organizador,
            caso,
        )

    caso.execute.assert_not_called()
    assert respuesta.status_code == 429
    assert json.loads(respuesta.body)["error_code"] == "INVITATION_USER_RATE_LIMIT"
    assert contados == [
        (
            "100/hour",
            "invitations-per-user",
            rate_limit.clave_de_usuario(str(organizador.id)),
        )
    ]
