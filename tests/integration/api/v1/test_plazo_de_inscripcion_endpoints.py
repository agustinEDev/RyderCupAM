"""
El plazo de inscripción por la API y contra Postgres (15 nov 2026).

| Caso | Situación                                                  | Qué pasa                                    |
|------|------------------------------------------------------------|---------------------------------------------|
| C2   | apuntarse a una pública pasado el plazo                    | 400 ENROLLMENT_DEADLINE_PASSED              |
| C2   | invitar pasado el plazo                                    | 400 ENROLLMENT_DEADLINE_PASSED              |
| C2   | aceptar una invitación pasado el plazo                     | 400 ENROLLMENT_DEADLINE_PASSED              |
| C3   | la vuelta del cierre                                       | CLOSED, por el plazo                        |
| C5   | ... y el organizador                                       | recibe ENROLLMENTS_CLOSED                   |
| C4   | un Stableford con el organizador sin franja                | sigue ACTIVE, UN ENROLLMENT_CLOSE_BLOCKED   |
| R1   | cerrada a mano y reabierta pasado el plazo                 | se entra, y la vuelta no la toca            |
| R2   | creada con el torneo hoy                                   | se entra                                    |
| R3   | movida más tarde                                           | se vuelve a entrar                          |

«Pasado el plazo» se monta en la base de datos: el torneo, hoy (el plazo fue ayer a
las 12:00), y abierta hace diez días.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config.cierre_de_inscripciones import CierreDeInscripciones
from tests.conftest import (
    _URL_DE_LA_BD_DE_TEST,
    create_authenticated_user,
    create_competition,
    estado_en_bd,
    set_auth_cookies,
    sql_en_la_bd_de_test,
)

pytestmark = pytest.mark.asyncio

CERRADA = {"detail": "La inscripción está cerrada.", "error_code": "ENROLLMENT_DEADLINE_PASSED"}


async def _usuario(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"plazo-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Pla", "Zo"
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _competicion(client: AsyncClient, stroke_play: bool = False) -> tuple[dict, dict]:
    organizador = await _usuario(client)
    inicio = date.today() + timedelta(days=30)
    datos = {
        "name": f"Plazo {uuid.uuid4().hex[:8]}",
        "start_date": inicio.isoformat(),
        "end_date": (inicio + timedelta(days=1)).isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "visibility": "PUBLIC",
    }
    if stroke_play:
        datos.update(tournament_type="STABLEFORD", stroke_play={"category_limits": [12.0]})
    return organizador, await create_competition(client, organizador["cookies"], datos)


async def _pasado_el_plazo(competicion: dict) -> None:
    """El torneo, hoy: el plazo fue ayer a las 12:00. Y abierta hace diez días."""
    hoy = date.today()
    await sql_en_la_bd_de_test(
        "UPDATE competitions SET start_date = :hoy, end_date = :fin, "
        "enrollment_opened_at = :abierta WHERE id = :id",
        hoy=hoy,
        fin=hoy + timedelta(days=1),
        abierta=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10),
        id=competicion["id"],
    )


async def _entra(client: AsyncClient, jugador: dict, competicion: dict):
    set_auth_cookies(client, jugador["cookies"])
    return await client.post(f"/api/v1/competitions/{competicion['id']}/enrollments", json={})


async def _avisos(client: AsyncClient, quien: dict, tipo: str) -> list[dict]:
    set_auth_cookies(client, quien["cookies"])
    feed = await client.get("/api/v1/users/me/feed")
    assert feed.status_code == 200, feed.text
    return [e for e in feed.json()["events"] if e["type"] == tipo]


async def _vuelta() -> None:
    """Una vuelta del cierre, contra la base de datos de este test."""
    motor = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        await CierreDeInscripciones(async_sessionmaker(bind=motor, expire_on_commit=False)).vuelta()
    finally:
        await motor.dispose()


async def _del_plazo(competicion: dict) -> tuple[bool, bool]:
    """Si la cerró el plazo, y si ya se avisó de que no se podía cerrar."""
    motor = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with motor.connect() as conn:
            fila = (
                await conn.execute(
                    text(
                        "SELECT enrollment_closed_by_deadline, enrollment_close_blocked_notified "
                        "FROM competitions WHERE id = :id"
                    ),
                    {"id": competicion["id"]},
                )
            ).one()
    finally:
        await motor.dispose()
    return fila[0], fila[1]


async def test_c2_pasado_el_plazo_no_se_apunta_nadie(client: AsyncClient):
    _, competicion = await _competicion(client)
    await _pasado_el_plazo(competicion)

    respuesta = await _entra(client, await _usuario(client), competicion)

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json() == CERRADA


async def test_c2_pasado_el_plazo_no_se_invita(client: AsyncClient):
    organizador, competicion = await _competicion(client)
    invitado = await _usuario(client)
    await _pasado_el_plazo(competicion)

    set_auth_cookies(client, organizador["cookies"])
    respuesta = await client.post(
        f"/api/v1/competitions/{competicion['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json() == CERRADA


async def test_c2_pasado_el_plazo_no_se_acepta_una_invitacion(client: AsyncClient):
    organizador, competicion = await _competicion(client)
    invitado = await _usuario(client)
    set_auth_cookies(client, organizador["cookies"])
    invitacion = await client.post(
        f"/api/v1/competitions/{competicion['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert invitacion.status_code == 201, invitacion.text
    await _pasado_el_plazo(competicion)

    set_auth_cookies(client, invitado["cookies"])
    respuesta = await client.post(
        f"/api/v1/invitations/{invitacion.json()['id']}/respond", json={"action": "ACCEPT"}
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json() == CERRADA


async def test_c3_c5_la_vuelta_la_cierra_y_avisa_al_organizador(client: AsyncClient):
    organizador, competicion = await _competicion(client)
    await _pasado_el_plazo(competicion)

    await _vuelta()

    assert await estado_en_bd(competicion["id"]) == "CLOSED"
    assert await _del_plazo(competicion) == (True, False)
    [aviso] = await _avisos(client, organizador, "ENROLLMENTS_CLOSED")
    assert aviso["payload"]["competition_id"] == competicion["id"]


async def test_c3_antes_del_plazo_la_vuelta_no_la_toca(client: AsyncClient):
    _, competicion = await _competicion(client)

    await _vuelta()

    assert await estado_en_bd(competicion["id"]) == "ACTIVE"


async def test_c4_sin_franja_sigue_abierta_y_se_avisa_una_vez(client: AsyncClient):
    """El organizador se inscribe al crearla y no tiene franja: no se puede cerrar."""
    organizador, competicion = await _competicion(client, stroke_play=True)
    await _pasado_el_plazo(competicion)

    await _vuelta()
    await _vuelta()

    assert await estado_en_bd(competicion["id"]) == "ACTIVE"
    assert await _del_plazo(competicion) == (False, True)
    [aviso] = await _avisos(client, organizador, "ENROLLMENT_CLOSE_BLOCKED")
    assert aviso["payload"]["reason"] == "NO_TEE_WINDOW"
    assert aviso["payload"]["player_count"] == 1
    # Y mientras, el plazo no deja entrar a nadie (C2)
    respuesta = await _entra(client, await _usuario(client), competicion)
    assert respuesta.status_code == 400, respuesta.text


async def test_r1_reabierta_pasado_el_plazo_se_entra_y_la_vuelta_no_la_toca(
    client: AsyncClient,
):
    organizador, competicion = await _competicion(client)
    await _pasado_el_plazo(competicion)
    set_auth_cookies(client, organizador["cookies"])
    cerrada = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
    assert cerrada.status_code == 200, cerrada.text

    reabierta = await client.post(f"/api/v1/competitions/{competicion['id']}/reopen-enrollments")
    assert reabierta.status_code == 200, reabierta.text

    respuesta = await _entra(client, await _usuario(client), competicion)
    assert respuesta.status_code == 201, respuesta.text
    await _vuelta()
    assert await estado_en_bd(competicion["id"]) == "ACTIVE"


async def test_r2_creada_para_hoy_se_entra(client: AsyncClient):
    organizador = await _usuario(client)
    hoy = date.today()
    competicion = await create_competition(
        client,
        organizador["cookies"],
        {
            "name": f"Hoy {uuid.uuid4().hex[:8]}",
            "start_date": hoy.isoformat(),
            "end_date": (hoy + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "visibility": "PUBLIC",
        },
    )

    respuesta = await _entra(client, await _usuario(client), competicion)

    assert respuesta.status_code == 201, respuesta.text


async def test_r3_movida_mas_tarde_se_vuelve_a_entrar(client: AsyncClient):
    organizador, competicion = await _competicion(client)
    await _pasado_el_plazo(competicion)
    inicio = date.today() + timedelta(days=10)

    set_auth_cookies(client, organizador["cookies"])
    movida = await client.put(
        f"/api/v1/competitions/{competicion['id']}",
        json={
            "start_date": inicio.isoformat(),
            "end_date": (inicio + timedelta(days=1)).isoformat(),
        },
    )
    assert movida.status_code == 200, movida.text

    respuesta = await _entra(client, await _usuario(client), competicion)
    assert respuesta.status_code == 201, respuesta.text
