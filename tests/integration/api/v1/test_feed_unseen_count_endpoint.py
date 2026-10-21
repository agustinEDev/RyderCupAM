"""
Tests E2E del contador de novedades: `GET /users/me/feed/unseen-count`.

Es la llamada ligera que el cliente hace al abrir la app y al volver a ella
para pintar el numero del boton de Actividad, sin cargar el feed entero.
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.helpers.feed_helper import (
    hacerse_amigos,
    insertar_eventos,
    marcar_visto,
)

URL = "/api/v1/users/me/feed/unseen-count"
VISITA = datetime(2026, 9, 14, 18, 0)
PASSWORD = "P@ssw0rd123!"


@pytest.mark.asyncio
async def test_devuelve_el_numero_de_novedades(client: AsyncClient):
    """
    Given un amigo con 2 logros publicados tras mi visita y 1 antes, y 1 mio
    nuevo / When pido el contador / Then 3.
    """
    ana = await create_authenticated_user(client, "cnt_a@test.com", PASSWORD, "Ana", "Garcia")
    luis = await create_authenticated_user(client, "cnt_b@test.com", PASSWORD, "Luis", "Perez")
    await hacerse_amigos(client, ana, luis)
    await marcar_visto(ana["user"]["id"], VISITA)
    await insertar_eventos(
        luis["user"]["id"],
        [VISITA - timedelta(hours=1), VISITA + timedelta(hours=1), VISITA + timedelta(hours=2)],
    )
    await insertar_eventos(ana["user"]["id"], [VISITA + timedelta(minutes=5)])

    set_auth_cookies(client, ana["cookies"])
    respuesta = await client.get(URL)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"unseen_count": 3}


@pytest.mark.asyncio
async def test_c12_se_queda_en_diez(client: AsyncClient):
    """C12. Given 12 novedades / When pido el contador / Then 10."""
    ana = await create_authenticated_user(client, "cnt_c@test.com", PASSWORD, "Ana", "Garcia")
    await marcar_visto(ana["user"]["id"], VISITA)
    await insertar_eventos(
        ana["user"]["id"], [VISITA + timedelta(minutes=i + 1) for i in range(12)]
    )

    set_auth_cookies(client, ana["cookies"])
    respuesta = await client.get(URL)

    assert respuesta.json() == {"unseen_count": 10}


@pytest.mark.asyncio
async def test_c16_coincide_con_el_del_feed(client: AsyncClient):
    """
    C16. Given novedades mias y de un amigo / When pido el contador y el feed
    / Then dan el mismo numero.
    """
    ana = await create_authenticated_user(client, "cnt_d@test.com", PASSWORD, "Ana", "Garcia")
    luis = await create_authenticated_user(client, "cnt_e@test.com", PASSWORD, "Luis", "Perez")
    await hacerse_amigos(client, ana, luis)
    await marcar_visto(ana["user"]["id"], VISITA)
    await insertar_eventos(luis["user"]["id"], [VISITA + timedelta(hours=1)])
    await insertar_eventos(ana["user"]["id"], [VISITA + timedelta(hours=2)])
    await insertar_eventos(
        luis["user"]["id"], [VISITA + timedelta(hours=3)], visible_to_friends=False
    )

    set_auth_cookies(client, ana["cookies"])
    contador = (await client.get(URL)).json()["unseen_count"]
    feed = (await client.get("/api/v1/users/me/feed")).json()

    assert contador == feed["unseen_count"] == 2


@pytest.mark.asyncio
async def test_c15_sin_sesion_da_401(client: AsyncClient):
    """C15. Given ninguna sesion / When se pide el contador / Then 401."""
    client.cookies.clear()

    respuesta = await client.get(URL)

    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_c15_pasado_el_limite_da_429(client: AsyncClient):
    """
    C15. Given un jugador que ya ha pedido el contador 120 veces en un minuto /
    When lo pide otra vez / Then 429: es una llamada barata, pero no gratis.
    """
    ana = await create_authenticated_user(client, "cnt_f@test.com", PASSWORD, "Ana", "Garcia")
    set_auth_cookies(client, ana["cookies"])

    for _ in range(120):
        assert (await client.get(URL)).status_code == 200
    respuesta = await client.get(URL)

    assert respuesta.status_code == 429
