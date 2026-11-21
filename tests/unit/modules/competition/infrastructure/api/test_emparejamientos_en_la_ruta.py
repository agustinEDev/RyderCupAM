"""
La ruta de generar partidos con un emparejamiento a mano fuera de su equipo
(tabla del 21 nov 2026, D): 422 PAIRING_PLAYER_NOT_IN_TEAM con un texto fijo.
"""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import GenerateMatchesBodyDTO
from src.modules.competition.application.exceptions import PairingPlayerNotInTeamError
from src.modules.competition.infrastructure.api.v1 import round_match_routes
from src.modules.user.application.dto.user_dto import UserResponseDTO


@pytest.mark.asyncio
async def test_generate_with_a_pairing_out_of_its_team_answers_422_with_a_fixed_text():
    """
    Given un caso de uso que rechaza un emparejamiento fuera de su equipo
    When llega a la ruta de generar partidos
    Then 422 PAIRING_PLAYER_NOT_IN_TEAM, sin el texto de la excepción
    """
    caso = AsyncMock()
    caso.execute.side_effect = PairingPlayerNotInTeamError("texto interno con datos")
    quien = UserResponseDTO.model_construct(id=uuid4(), email="o@test.com", is_admin=False)

    respuesta = await round_match_routes.generate_matches.__wrapped__(
        MagicMock(), uuid4(), GenerateMatchesBodyDTO(manual_pairings=[]), quien, caso
    )

    assert respuesta.status_code == 422
    assert json.loads(respuesta.body) == {
        "detail": "Each paired player must be on their own team's side.",
        "error_code": "PAIRING_PLAYER_NOT_IN_TEAM",
    }
