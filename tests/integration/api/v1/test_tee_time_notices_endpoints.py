"""
El aviso de horario de punta a punta (G, 22 oct 2026): la API genera las
partidas, el aviso llega al feed de cada jugador con su hora y su grupo, y
borrar las partidas lo retira. Cubre el cableado real, sesion de Actividad
incluida, que los tests de caso de uso montan a mano.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_tee_groups_endpoints import _generar, _stableford

pytestmark = pytest.mark.asyncio


async def _avisos_de_salida(client: AsyncClient, jugador: dict) -> list[dict]:
    set_auth_cookies(client, jugador["cookies"])
    respuesta = await client.get("/api/v1/users/me/feed")
    assert respuesta.status_code == 200, respuesta.text
    return [e for e in respuesta.json()["events"] if e["type"] == "TEE_TIME_ASSIGNED"]


async def test_generating_the_groups_notifies_each_player(client: AsyncClient):
    organizador, competicion, franja, jugadores = await _stableford(client)

    generadas = await _generar(client, organizador, franja)
    assert generadas.status_code == 200, generadas.text

    (partida,) = generadas.json()["groups"]
    ids = {p["user_id"] for p in partida["players"]}
    (aviso,) = await _avisos_de_salida(client, jugadores[0])
    payload = aviso["payload"]
    assert aviso["source_match_id"] == franja
    assert payload["competition_id"] == competicion["id"]
    assert payload["round_id"] == franja
    assert payload["round_date"] == competicion["start_date"]
    assert payload["session_type"] == "MORNING"
    assert payload["kind"] == "TEE_GROUP"
    assert payload["tee_time"] == "09:00"
    assert set(payload["partner_ids"]) == ids - {jugadores[0]["user"]["id"]}
    assert payload["opponent_ids"] == []
    assert payload["match_id"] is None
    assert payload["changed"] is False


async def test_deleting_the_groups_withdraws_the_notices(client: AsyncClient):
    organizador, _, franja, jugadores = await _stableford(client)
    assert (await _generar(client, organizador, franja)).status_code == 200

    set_auth_cookies(client, organizador["cookies"])
    borradas = await client.delete(f"/api/v1/competitions/rounds/{franja}/groups")

    assert borradas.status_code == 204, borradas.text
    assert await _avisos_de_salida(client, jugadores[0]) == []
    assert await _avisos_de_salida(client, organizador) == []
