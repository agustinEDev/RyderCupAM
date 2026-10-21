"""Tests E2E: el feed lleva la fecha de publicacion de cada entrada."""

from datetime import datetime

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.helpers.feed_helper import insertar_eventos

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
