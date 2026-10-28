"""
Inscripción directa en las públicas, por la API (release social 3, tabla del 28 oct 2026).
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
        client, f"dir-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Di", "Recta"
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _publica(client: AsyncClient, stroke_play: bool) -> tuple[dict, dict]:
    organizador = await _usuario(client)
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Dir {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "visibility": "PUBLIC",
    }
    if stroke_play:
        datos.update(tournament_type="STABLEFORD", stroke_play={"category_limits": [12.0]})
    competicion = await create_competition(client, organizador["cookies"], datos)
    return organizador, competicion


async def _franja_de_tres(client: AsyncClient, organizador: dict, competicion: dict) -> str:
    """Una franja de una sola salida de 3: cupo 3."""
    franja = await add_one_session(client, organizador["cookies"], competicion)
    set_auth_cookies(client, organizador["cookies"])
    respuesta = await client.put(
        f"/api/v1/competitions/rounds/{franja['id']}",
        json={
            "tee_sheet": {
                "first_tee_time": "09:00",
                "last_tee_time": "09:00",
                "interval_minutes": 10,
                "group_size": 3,
            }
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return franja["id"]


async def _entra(client: AsyncClient, jugador: dict, competicion: dict, **cuerpo):
    set_auth_cookies(client, jugador["cookies"])
    return await client.post(f"/api/v1/competitions/{competicion['id']}/enrollments", json=cuerpo)


async def _avisos(client: AsyncClient, quien: dict, tipo: str) -> list[dict]:
    set_auth_cookies(client, quien["cookies"])
    feed = await client.get("/api/v1/users/me/feed")
    assert feed.status_code == 200, feed.text
    return [e for e in feed.json()["events"] if e["type"] == tipo]


async def _llena(client, organizador, competicion, franja) -> list[dict]:
    """El organizador (inscrito al crearla) y dos más: la franja de 3, llena."""
    set_auth_cookies(client, organizador["cookies"])
    cogida = await client.post(f"/api/v1/competitions/rounds/{franja}/places", json={})
    assert cogida.status_code == 201, cogida.text
    dentro = []
    for _ in range(2):
        jugador = await _usuario(client)
        respuesta = await _entra(client, jugador, competicion, round_id=franja)
        assert respuesta.status_code == 201, respuesta.text
        dentro.append(jugador)
    return dentro


async def test_en_una_ryder_publica_se_entra_y_el_organizador_se_entera(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=False)
    jugador = await _usuario(client)

    respuesta = await _entra(client, jugador, competicion, tee_color="WHITE")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["status"] == "APPROVED"
    [aviso] = await _avisos(client, organizador, "PLAYER_JOINED")
    assert aviso["payload"]["player_id"] == jugador["user"]["id"]
    assert aviso["payload"]["waiting"] is False


async def test_con_franjas_hay_que_elegir_una(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    await _franja_de_tres(client, organizador, competicion)
    jugador = await _usuario(client)

    respuesta = await _entra(client, jugador, competicion)

    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == "TEE_WINDOW_REQUIRED"


async def test_con_hueco_entra_con_su_plaza(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    jugador = await _usuario(client)

    respuesta = await _entra(client, jugador, competicion, round_id=franja)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["round_id"] == franja
    assert respuesta.json()["waiting"] is False
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()
    hoja = calendario["days"][0]["rounds"][0]["tee_sheet"]
    assert hoja["places_taken"] == 1


async def test_llena_sin_espera_409_y_con_espera_entra_esperando(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    await _llena(client, organizador, competicion, franja)
    jugador = await _usuario(client)

    sin_espera = await _entra(client, jugador, competicion, round_id=franja)
    con_espera = await _entra(client, jugador, competicion, round_id=franja, waiting_list=True)

    assert sin_espera.status_code == 409, sin_espera.text
    assert sin_espera.json()["error_code"] == "TEE_WINDOW_FULL"
    assert con_espera.status_code == 201, con_espera.text
    assert con_espera.json()["waiting"] is True
    [aviso] = [
        a
        for a in await _avisos(client, organizador, "PLAYER_JOINED")
        if a["payload"]["player_id"] == jugador["user"]["id"]
    ]
    assert aviso["payload"]["waiting"] is True
    assert aviso["payload"]["round_id"] == franja


async def test_la_espera_de_una_franja_con_hueco_409(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    jugador = await _usuario(client)

    respuesta = await _entra(client, jugador, competicion, round_id=franja, waiting_list=True)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "TEE_WINDOW_HAS_ROOM"


async def test_al_soltarse_una_plaza_el_que_espera_entra_y_se_le_avisa(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    dentro = await _llena(client, organizador, competicion, franja)
    espera = await _usuario(client)
    await _entra(client, espera, competicion, round_id=franja, waiting_list=True)

    set_auth_cookies(client, dentro[0]["cookies"])
    soltada = await client.delete(
        f"/api/v1/competitions/rounds/{franja}/places/{dentro[0]['user']['id']}"
    )

    assert soltada.status_code == 204, soltada.text
    [aviso] = await _avisos(client, espera, "PLACE_FROM_WAITING_LIST")
    assert aviso["payload"]["round_id"] == franja
    assert aviso["payload"]["tee_time"] == "09:00"


async def test_dejar_la_ultima_espera_saca_de_la_competicion(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    await _llena(client, organizador, competicion, franja)
    espera = await _usuario(client)
    await _entra(client, espera, competicion, round_id=franja, waiting_list=True)

    set_auth_cookies(client, espera["cookies"])
    fuera = await client.delete(
        f"/api/v1/competitions/rounds/{franja}/waiting-list/{espera['user']['id']}"
    )
    otra_vez = await _entra(client, espera, competicion, round_id=franja, waiting_list=True)

    assert fuera.status_code == 204, fuera.text
    # Salió: puede volver a entrar con su fila reutilizada
    assert otra_vez.status_code == 201, otra_vez.text


async def test_al_cerrar_quien_sigue_en_espera_sale_sin_plaza(client: AsyncClient):
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    await _llena(client, organizador, competicion, franja)
    espera = await _usuario(client)
    esperando = await _entra(client, espera, competicion, round_id=franja, waiting_list=True)
    assert esperando.status_code == 201, esperando.text

    set_auth_cookies(client, organizador["cookies"])
    cerrada = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")

    assert cerrada.status_code == 200, cerrada.text
    [aviso] = await _avisos(client, espera, "ENROLLMENT_NO_PLACE")
    assert aviso["payload"]["competition_id"] == competicion["id"]
    set_auth_cookies(client, organizador["cookies"])
    inscritos = await client.get(f"/api/v1/competitions/{competicion['id']}/enrollments")
    suya = [i for i in inscritos.json() if i["user_id"] == espera["user"]["id"]]
    assert [i["status"] for i in suya] == ["WITHDRAWN"]


async def test_al_cerrar_al_que_sale_sin_plaza_no_se_le_fija_handicap(client: AsyncClient):
    """Revisor (28 oct 2026): el que sale al cerrar no cuenta para los hándicaps fijados."""
    organizador, competicion = await _publica(client, stroke_play=True)
    franja = await _franja_de_tres(client, organizador, competicion)
    await _llena(client, organizador, competicion, franja)
    espera = await _usuario(client)
    await _entra(client, espera, competicion, round_id=franja, waiting_list=True)

    set_auth_cookies(client, organizador["cookies"])
    cerrada = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    inscritos = await client.get(f"/api/v1/competitions/{competicion['id']}/enrollments")

    assert cerrada.status_code == 200, cerrada.text
    por_usuario = {i["user_id"]: i for i in inscritos.json()}
    assert por_usuario[espera["user"]["id"]]["fixed_handicap"] is None
    assert all(
        i["fixed_handicap"] is not None for u, i in por_usuario.items() if i["status"] == "APPROVED"
    )
