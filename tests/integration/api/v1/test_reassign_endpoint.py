"""
Errores de reasignar jugadores por la API (BE #477).

Desde que reasignar usa el mismo reparto que generar, una barra sin valorar
lanza `TeeColorNotFoundError`, como al generar. Antes era un ValueError suelto
que la ruta convertía en un 500 «inesperado».
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def test_a_tee_without_rating_is_a_400_with_its_message(client: AsyncClient):
    """
    El caso de uso se sustituye por uno que lanza el error: la regla ya la
    cubren sus tests, aquí solo importa cómo la traduce la ruta.
    """
    from main import app
    from src.config.dependencies import get_reassign_match_players_use_case
    from src.modules.competition.application.services.match_players_builder import (
        TeeColorNotFoundError,
    )

    class _SinBarra:
        async def execute(self, *args, **kwargs):
            raise TeeColorNotFoundError("No se encontró tee rating para color 'RED'")

    usuario = await create_authenticated_user(
        client, "reasignar-1@test.com", "P@ssw0rd123!", "Reasignar", "Uno"
    )
    set_auth_cookies(client, usuario["cookies"])
    app.dependency_overrides[get_reassign_match_players_use_case] = _SinBarra
    try:
        respuesta = await client.put(
            f"/api/v1/competitions/matches/{uuid4()}/players",
            json={"team_a_player_ids": [str(uuid4())], "team_b_player_ids": [str(uuid4())]},
        )
    finally:
        app.dependency_overrides.pop(get_reassign_match_players_use_case, None)

    assert respuesta.status_code == 400, respuesta.text
    assert "tee rating" in respuesta.json()["detail"]
