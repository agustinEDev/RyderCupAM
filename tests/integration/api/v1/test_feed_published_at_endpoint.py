"""Tests E2E: el feed lleva la fecha de publicacion de cada entrada."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.helpers.feed_helper import hacerse_amigos, insertar_eventos

PUBLICADO = datetime(2026, 9, 14, 18, 30, 5)


@pytest.mark.asyncio
async def test_published_at_sale_en_utc_con_z(client: AsyncClient):
    """
    Given un logro publicado / When pido el feed / Then `published_at` viaja en
    UTC y con «Z»: sin zona, el navegador la tomaria por hora local y la
    pintaria desplazada.
    """
    ana = await create_authenticated_user(client, "pubz@test.com", "P@ssw0rd123!", "Ana", "Garcia")
    await insertar_eventos(ana["user"]["id"], [PUBLICADO])

    set_auth_cookies(client, ana["cookies"])
    respuesta = await client.get("/api/v1/users/me/feed")

    assert respuesta.status_code == 200
    [evento] = respuesta.json()["events"]
    assert evento["published_at"] == "2026-09-14T18:30:05Z"


@pytest.mark.asyncio
async def test_occurred_at_tambien_sale_en_utc_con_z(client: AsyncClient):
    """
    Given un logro / When pido el feed / Then `occurred_at` tambien lleva «Z»:
    se guarda en UTC sin zona, y sin ella el navegador la leeria como local.
    """
    ana = await create_authenticated_user(client, "occz@test.com", "P@ssw0rd123!", "Ana", "Garcia")
    await insertar_eventos(ana["user"]["id"], [PUBLICADO])

    set_auth_cookies(client, ana["cookies"])
    respuesta = await client.get("/api/v1/users/me/feed")

    [evento] = respuesta.json()["events"]
    assert evento["occurred_at"] == "2026-09-14T18:30:05Z"


@pytest.mark.asyncio
async def test_la_actividad_vista_por_un_amigo_no_trae_lo_oculto(client: AsyncClient):
    """
    Given un jugador con un logro visible y otro publicado oculto / When su
    amigo pide su actividad / Then solo le llega el visible; el propio jugador
    ve los dos.
    """
    ana = await create_authenticated_user(client, "ocu_a@test.com", "P@ssw0rd123!", "Ana", "Garcia")
    luis = await create_authenticated_user(
        client, "ocu_b@test.com", "P@ssw0rd123!", "Luis", "Perez"
    )
    await hacerse_amigos(client, ana, luis)
    await insertar_eventos(ana["user"]["id"], [PUBLICADO])
    await insertar_eventos(
        ana["user"]["id"], [PUBLICADO + timedelta(hours=1)], visible_to_friends=False
    )

    set_auth_cookies(client, luis["cookies"])
    vista_amigo = await client.get(f"/api/v1/users/{ana['user']['id']}/activity")
    set_auth_cookies(client, ana["cookies"])
    vista_propia = await client.get(f"/api/v1/users/{ana['user']['id']}/activity")

    assert vista_amigo.status_code == 200
    assert [e["published_at"] for e in vista_amigo.json()["events"]] == ["2026-09-14T18:30:05Z"]
    assert len(vista_propia.json()["events"]) == 2
