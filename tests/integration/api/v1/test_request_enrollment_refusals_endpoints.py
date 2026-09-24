"""
Pedir plaza en una pública, de verdad contra la API (BE #372).

Lo que un test unitario no ve: que el día del torneo la ruta deja pasar, y que
los «no» llegan como 400 con su motivo y no como un 500, que el navegador toma
por un fallo de red (sin cabeceras de CORS) y deja al jugador sin respuesta.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import _URL_DE_LA_BD_DE_TEST
from tests.integration.api.v1.helpers.auth_helper import create_and_login_user

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _jugador(client: AsyncClient, nombre: str):
    _, cookies = await create_and_login_user(
        client,
        email=f"{nombre}_{uuid4()}@test.com",
        password="SecurePass123!",
        first_name=nombre.capitalize(),
        last_name="Club",
    )
    return cookies


async def _publica(client: AsyncClient, empieza: date, max_players: int = 12):
    organiza = await _jugador(client, "organiza")
    creada = await client.post(
        "/api/v1/competitions",
        json={
            "name": f"Club {uuid4().hex[:6]}",
            "start_date": empieza.isoformat(),
            "end_date": (empieza + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": max_players,
            "visibility": "PUBLIC",
        },
        cookies=organiza,
    )
    assert creada.status_code == 201, creada.text
    return creada.json()["id"], organiza


async def _pide(client: AsyncClient, competicion_id: str, cookies):
    return await client.post(
        f"/api/v1/competitions/{competicion_id}/enrollments",
        json={"type": "REQUEST"},
        cookies=cookies,
    )


async def test_el_dia_del_torneo_se_pide_plaza(client: AsyncClient):
    competicion_id, _ = await _publica(client, date.today())

    respuesta = await _pide(client, competicion_id, await _jugador(client, "tarde"))

    assert respuesta.status_code == 201, respuesta.text


async def test_empezado_el_torneo_es_un_400_con_el_motivo(client: AsyncClient):
    competicion_id, _ = await _publica(client, date.today())
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE competitions SET start_date = :d WHERE id = :id"),
                {"d": date.today() - timedelta(days=1), "id": competicion_id},
            )
    finally:
        await engine.dispose()

    respuesta = await _pide(client, competicion_id, await _jugador(client, "tarde"))

    assert respuesta.status_code == 400, respuesta.text
    assert "ya ha empezado" in respuesta.json()["detail"]


async def test_llena_es_un_400_con_el_motivo(client: AsyncClient):
    competicion_id, organiza = await _publica(
        client, date.today() + timedelta(days=5), max_players=2
    )
    # El organizador ya ocupa una plaza: con otro aprobado, se llena
    otro = await _pide(client, competicion_id, await _jugador(client, "otro"))
    assert otro.status_code == 201, otro.text
    aprobado = await client.post(
        f"/api/v1/enrollments/{otro.json()['id']}/approve", cookies=organiza
    )
    assert aprobado.status_code == 200, aprobado.text

    respuesta = await _pide(client, competicion_id, await _jugador(client, "ultimo"))

    assert respuesta.status_code == 400, respuesta.text
    assert "completa" in respuesta.json()["detail"]


async def test_aprobar_con_la_competicion_llena_es_un_400_con_el_motivo(client: AsyncClient):
    """El gemelo del organizador: el día del torneo puede haber más solicitudes
    pendientes que plazas, y aprobar la que sobra reventaba igual."""
    competicion_id, organiza = await _publica(
        client, date.today() + timedelta(days=5), max_players=2
    )
    primera = await _pide(client, competicion_id, await _jugador(client, "primera"))
    segunda = await _pide(client, competicion_id, await _jugador(client, "segunda"))
    assert primera.status_code == segunda.status_code == 201
    aprobada = await client.post(
        f"/api/v1/enrollments/{primera.json()['id']}/approve", cookies=organiza
    )
    assert aprobada.status_code == 200, aprobada.text

    respuesta = await client.post(
        f"/api/v1/enrollments/{segunda.json()['id']}/approve", cookies=organiza
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "completa" in respuesta.json()["detail"]
