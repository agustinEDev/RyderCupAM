"""
La clasificación por enlace, sin sesión (release social 3, tabla del 28 oct 2026).
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import add_one_session, create_authenticated_user, create_competition

pytestmark = pytest.mark.asyncio


async def _competicion(client: AsyncClient, visibilidad: str, stroke_play: bool) -> dict:
    organizador = await create_authenticated_user(
        client, f"vis-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Vi", "Sitante"
    )
    if stroke_play:
        respuesta = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": organizador["user"]["id"], "manual_handicap": 15.0},
            cookies=organizador["cookies"],
        )
        assert respuesta.status_code == 200, respuesta.text
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Vis {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "visibility": visibilidad,
    }
    if stroke_play:
        datos.update(tournament_type="MEDAL", stroke_play={"category_limits": [12.0]})
    competicion = await create_competition(client, organizador["cookies"], datos)
    franja = await add_one_session(client, organizador["cookies"], competicion)
    client.cookies.clear()
    return {**competicion, "franja": franja["id"]}


def _rutas(competicion: dict, stroke_play: bool) -> list[str]:
    if not stroke_play:
        return [f"/api/v1/competitions/{competicion['id']}/leaderboard"]
    base = f"/api/v1/competitions/{competicion['id']}"
    return [
        f"{base}/standings",
        f"{base}/standings/scratch",
        f"/api/v1/competitions/rounds/{competicion['franja']}/standings",
    ]


@pytest.mark.parametrize("stroke_play", [False, True])
async def test_l1_l2_una_publica_se_ve_sin_sesion(client: AsyncClient, stroke_play):
    competicion = await _competicion(client, "PUBLIC", stroke_play)

    for ruta in _rutas(competicion, stroke_play):
        respuesta = await client.get(ruta)
        assert respuesta.status_code == 200, (ruta, respuesta.text)


@pytest.mark.parametrize("stroke_play", [False, True])
async def test_l3_una_privada_no_sin_sesion(client: AsyncClient, stroke_play):
    competicion = await _competicion(client, "PRIVATE", stroke_play)

    for ruta in _rutas(competicion, stroke_play):
        respuesta = await client.get(ruta)
        assert respuesta.status_code == 403, (ruta, respuesta.text)
        assert respuesta.json()["error_code"] == "PRIVATE_COMPETITION"


@pytest.mark.parametrize("visibilidad", ["PUBLIC", "PRIVATE"])
async def test_l5_el_resumen_sin_sesion(client: AsyncClient, visibilidad):
    competicion = await _competicion(client, visibilidad, stroke_play=True)

    respuesta = await client.get(f"/api/v1/competitions/{competicion['id']}/summary")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["name"] == competicion["name"]
    assert cuerpo["tournament_type"] == "MEDAL"
    assert cuerpo["has_teams"] is False
    assert cuerpo["visibility"] == visibilidad


async def test_l5_el_resumen_de_una_que_no_existe(client: AsyncClient):
    respuesta = await client.get(f"/api/v1/competitions/{uuid.uuid4()}/summary")

    assert respuesta.status_code == 404, respuesta.text


async def test_l6_la_ficha_sigue_pidiendo_sesion(client: AsyncClient):
    competicion = await _competicion(client, "PUBLIC", stroke_play=False)

    respuesta = await client.get(f"/api/v1/competitions/{competicion['id']}")

    assert respuesta.status_code == 401, respuesta.text


async def test_con_un_token_que_no_vale_es_un_401_no_un_visitante(client: AsyncClient):
    competicion = await _competicion(client, "PUBLIC", stroke_play=False)
    client.cookies.set("access_token", "no-es-un-token")

    respuesta = await client.get(f"/api/v1/competitions/{competicion['id']}/leaderboard")

    assert respuesta.status_code == 401, respuesta.text
