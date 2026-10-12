"""
Las plazas en las franjas por la API (#251, decidido el 6-8 oct 2026).
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio


async def _usuario(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"pla-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Pla", "Za"
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _stableford_con_franja(client: AsyncClient) -> tuple[dict, dict, str]:
    organizador = await _usuario(client)
    start = date.today() + timedelta(days=30)
    competicion = await create_competition(
        client,
        organizador["cookies"],
        {
            "name": f"Pla {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "tournament_type": "STABLEFORD",
            "stroke_play": {"category_limits": [12.0]},
        },
    )
    franja = await add_one_session(client, organizador["cookies"], competicion)
    return organizador, competicion, franja["id"]


async def _jugador_aprobado(client: AsyncClient, organizador: dict, competicion: dict) -> dict:
    jugador = await _usuario(client)
    set_auth_cookies(client, organizador["cookies"])
    respuesta = await client.post(
        f"/api/v1/competitions/{competicion['id']}/enrollments/direct",
        json={"competition_id": competicion["id"], "user_id": jugador["user"]["id"]},
    )
    assert respuesta.status_code in (200, 201), respuesta.text
    return jugador


async def _quien_va(client: AsyncClient, competicion: dict) -> list[str]:
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()
    return calendario["days"][0]["rounds"][0]["tee_sheet"]["player_ids"]


async def test_el_jugador_coge_y_suelta_su_plaza(client: AsyncClient):
    organizador, competicion, franja = await _stableford_con_franja(client)
    jugador = await _jugador_aprobado(client, organizador, competicion)
    set_auth_cookies(client, jugador["cookies"])

    cogida = await client.post(f"/api/v1/competitions/rounds/{franja}/places", json={})
    tras_coger = await _quien_va(client, competicion)
    soltada = await client.delete(
        f"/api/v1/competitions/rounds/{franja}/places/{jugador['user']['id']}"
    )

    assert cogida.status_code == 201, cogida.text
    assert tras_coger == [jugador["user"]["id"]]
    assert soltada.status_code == 204, soltada.text
    assert await _quien_va(client, competicion) == []


async def test_otro_jugador_no_puede_coger_por_el(client: AsyncClient):
    organizador, competicion, franja = await _stableford_con_franja(client)
    jugador = await _jugador_aprobado(client, organizador, competicion)
    otro = await _usuario(client)

    respuesta = await client.post(
        f"/api/v1/competitions/rounds/{franja}/places",
        json={"user_id": jugador["user"]["id"]},
    )

    assert otro and respuesta.status_code == 403, respuesta.text


async def test_cerrar_con_un_aprobado_sin_franja_es_un_400_con_la_lista(client: AsyncClient):
    organizador, competicion, franja = await _stableford_con_franja(client)
    set_auth_cookies(client, organizador["cookies"])
    # El organizador está inscrito al crearla; aún no tiene franja

    respuesta = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    colocado = await client.post(
        f"/api/v1/competitions/rounds/{franja}/places",
        json={"user_id": organizador["user"]["id"]},
    )
    cerrada = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")

    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "PLAYERS_WITHOUT_TEE_WINDOW"
    assert [p["missing"] for p in cuerpo["players"]] == ["TEE_WINDOW"]
    assert colocado.status_code == 201, colocado.text
    assert cerrada.status_code == 200, cerrada.text


async def test_borrar_una_franja_con_gente_dentro_es_un_400(client: AsyncClient):
    organizador, _, franja = await _stableford_con_franja(client)
    set_auth_cookies(client, organizador["cookies"])
    await client.post(f"/api/v1/competitions/rounds/{franja}/places", json={})

    respuesta = await client.delete(f"/api/v1/competitions/rounds/{franja}")

    assert respuesta.status_code == 400, respuesta.text
    assert "plaza" in respuesta.json()["detail"]


async def test_la_lista_de_espera_de_punta_a_punta(client: AsyncClient):
    """Llena, alguien espera, se libera una plaza: se le asigna y lo ve hasta «Entendido»."""
    organizador, competicion, franja = await _stableford_con_franja(client)
    set_auth_cookies(client, organizador["cookies"])
    una_salida_de_3 = {
        "first_tee_time": "09:00",
        "last_tee_time": "09:00",
        "interval_minutes": 10,
        "group_size": 3,
    }
    cambio = await client.put(
        f"/api/v1/competitions/rounds/{franja}", json={"tee_sheet": una_salida_de_3}
    )
    assert cambio.status_code == 200, cambio.text
    dentro = [await _jugador_aprobado(client, organizador, competicion) for _ in range(3)]
    for jugador in dentro:
        set_auth_cookies(client, jugador["cookies"])
        assert (
            await client.post(f"/api/v1/competitions/rounds/{franja}/places", json={})
        ).status_code == 201
    espera = await _jugador_aprobado(client, organizador, competicion)
    set_auth_cookies(client, espera["cookies"])

    apuntado = await client.post(f"/api/v1/competitions/rounds/{franja}/waiting-list")
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()
    set_auth_cookies(client, dentro[0]["cookies"])
    await client.delete(f"/api/v1/competitions/rounds/{franja}/places/{dentro[0]['user']['id']}")
    set_auth_cookies(client, espera["cookies"])
    asignadas = (await client.get("/api/v1/competitions/me/assigned-places")).json()
    entendido = await client.post(f"/api/v1/competitions/me/assigned-places/{franja}/acknowledge")
    despues = (await client.get("/api/v1/competitions/me/assigned-places")).json()

    assert apuntado.status_code == 201, apuntado.text
    assert calendario["days"][0]["rounds"][0]["tee_sheet"]["waiting_ids"] == [espera["user"]["id"]]
    assert [a["round_id"] for a in asignadas] == [franja]
    assert entendido.status_code == 204, entendido.text
    assert despues == []
