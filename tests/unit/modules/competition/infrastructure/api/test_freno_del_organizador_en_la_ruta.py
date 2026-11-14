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
