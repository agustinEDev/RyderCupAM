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


async def test_reordering_tells_both_groups_their_new_hour(client: AsyncClient):
    """G3 de punta a punta: la publicacion relee la ronda en Postgres y compara."""
    organizador, _, franja, jugadores = await _stableford(client, jugadores=7)
    generadas = await _generar(client, organizador, franja)
    assert generadas.status_code == 200, generadas.text
    primera, segunda = generadas.json()["groups"]
    quien = primera["players"][0]["user_id"]
    del_jugador = next(j for j in [organizador, *jugadores] if j["user"]["id"] == quien)
    (antes,) = await _avisos_de_salida(client, del_jugador)

    set_auth_cookies(client, organizador["cookies"])
    reordenadas = await client.put(
        f"/api/v1/competitions/rounds/{franja}/groups/order",
        json={"group_ids": [segunda["id"], primera["id"]]},
    )
    assert reordenadas.status_code == 200, reordenadas.text

    (despues,) = await _avisos_de_salida(client, del_jugador)
    assert despues["id"] != antes["id"]
    assert (despues["payload"]["tee_time"], despues["payload"]["changed"]) == ("09:10", True)


async def test_generating_the_same_groups_again_leaves_the_notices(client: AsyncClient):
    organizador, _, franja, jugadores = await _stableford(client)
    assert (await _generar(client, organizador, franja)).status_code == 200
    (antes,) = await _avisos_de_salida(client, jugadores[0])

    assert (await _generar(client, organizador, franja)).status_code == 200

    (despues,) = await _avisos_de_salida(client, jugadores[0])
    assert despues["id"] == antes["id"]
