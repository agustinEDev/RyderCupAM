"""
E23. Las consultas del feed no crecen con los amigos ni con los eventos.

Se cuentan las sentencias que llegan a Postgres durante la peticion: con un
amigo y un logro, y con cuatro amigos y tres logros cada uno, tienen que ser
las mismas.
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.conftest import create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.helpers.feed_helper import hacerse_amigos, insertar_eventos

PASSWORD = "P@ssw0rd123!"
CUANDO = datetime(2026, 9, 14, 18, 0)


async def _sentencias_del_feed(client: AsyncClient, yo: dict) -> int:
    sentencias: list[str] = []

    def _cuenta(conn, cursor, statement, *args):
        sentencias.append(statement)

    set_auth_cookies(client, yo["cookies"])
    event.listen(Engine, "before_cursor_execute", _cuenta)
    try:
        respuesta = await client.get("/api/v1/users/me/feed")
    finally:
        event.remove(Engine, "before_cursor_execute", _cuenta)
    assert respuesta.status_code == 200
    return len(sentencias)


async def _con_amigos(client: AsyncClient, prefijo: str, amigos: int, logros: int) -> int:
    yo = await create_authenticated_user(
        client, f"{prefijo}_yo@test.com", PASSWORD, "Ana", "Garcia"
    )
    for i in range(amigos):
        amigo = await create_authenticated_user(
            client, f"{prefijo}_{i}@test.com", PASSWORD, "Luis", "Perez"
        )
        await hacerse_amigos(client, yo, amigo)
        await insertar_eventos(
            amigo["user"]["id"], [CUANDO - timedelta(minutes=j) for j in range(logros)]
        )
    return await _sentencias_del_feed(client, yo)


@pytest.mark.asyncio
async def test_e23_mismas_consultas_con_mas_amigos_y_eventos(client: AsyncClient):
    """
    E23. Given un jugador con 1 amigo y 1 logro, y otro con 4 amigos y 3
    logros cada uno / When piden el feed / Then cuesta las mismas consultas.
    """
    poco = await _con_amigos(client, "qc_poco", amigos=1, logros=1)
    mucho = await _con_amigos(client, "qc_mucho", amigos=4, logros=3)

    assert mucho == poco
