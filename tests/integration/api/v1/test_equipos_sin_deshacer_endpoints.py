"""
Mover a un jugador de equipo y generar con los equipos cambiados, por la API
(release social 3, T3 y T5, 28 oct 2026).
"""

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_generate_matches_block import _fourball_de_uno_contra_uno

pytestmark = pytest.mark.asyncio


async def _mover(client: AsyncClient, montaje: dict, user_id: str, equipo: str):
    return await client.put(
        f"/api/v1/competitions/{montaje['comp_id']}/teams/players/{user_id}",
        json={"team": equipo},
    )


async def _equipos(client: AsyncClient, montaje: dict) -> tuple[str, str]:
    set_auth_cookies(client, montaje["creador"]["cookies"])
    inscritos = (await client.get(f"/api/v1/competitions/{montaje['comp_id']}/enrollments")).json()
    return tuple(i["user_id"] for i in inscritos if i["status"] == "APPROVED")


async def test_t3_el_organizador_mueve_y_t5_generar_con_dos_de_diferencia_no(client: AsyncClient):
    montaje = await _fourball_de_uno_contra_uno(client)
    uno, otro = await _equipos(client, montaje)

    movido = await _mover(client, montaje, uno, "B")
    otra_vez = await _mover(client, montaje, otro, "B")
    generar = await client.post(
        f"/api/v1/competitions/rounds/{montaje['round_id']}/matches/generate", json={}
    )

    assert movido.status_code == 200, movido.text
    assert otra_vez.status_code == 200, otra_vez.text
    assert otra_vez.json()["team_a_player_ids"] == []
    assert sorted(otra_vez.json()["team_b_player_ids"]) == sorted([uno, otro])
    assert generar.status_code == 400, generar.text
    assert generar.json()["match_generation_block"]["reason"] == "TEAMS_UNBALANCED"


async def test_t3_a_quien_no_esta_inscrito_409(client: AsyncClient):
    montaje = await _fourball_de_uno_contra_uno(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    respuesta = await _mover(client, montaje, montaje["creador"]["user"]["id"], "A")

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "TEAMS_LOCKED"


async def test_t3_sin_organizar_403(client: AsyncClient):
    montaje = await _fourball_de_uno_contra_uno(client)
    uno, _ = await _equipos(client, montaje)
    from tests.conftest import create_authenticated_user

    otro = await create_authenticated_user(
        client, "mover_fuera@test.com", "P@ssw0rd123!", "Mo", "Ver"
    )
    set_auth_cookies(client, otro["cookies"])

    respuesta = await _mover(client, montaje, uno, "B")

    assert respuesta.status_code == 403, respuesta.text
