"""
Ayudas para los tests de punta a punta del feed.

Los logros solo nacen al cerrar una partida, y montar una entera por test
taparia lo que se prueba. Se escriben directamente en la base de datos del
test, con la fecha de publicacion que pida cada caso.
"""

import json
import uuid
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import _URL_DE_LA_BD_DE_TEST, set_auth_cookies


async def hacerse_amigos(client: AsyncClient, a: dict, b: dict) -> None:
    """a envia solicitud, b la acepta."""
    set_auth_cookies(client, a["cookies"])
    respuesta = await client.post(
        "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
    )
    friendship_id = respuesta.json()["id"]

    set_auth_cookies(client, b["cookies"])
    await client.post(
        f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
    )


async def insertar_eventos(
    user_id: str,
    publicados: list[datetime],
    tipo: str = "BIRDIE",
    visible_to_friends: bool = True,
) -> None:
    """Un logro por fecha de publicacion, cada uno de una partida distinta."""
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            for publicado in publicados:
                await conn.execute(
                    text(
                        "INSERT INTO activity_events (id, user_id, type, occurred_at, "
                        "published_at, visible_to_friends, payload, source_match_id) "
                        "VALUES (:id, :user_id, :type, :occurred_at, :published_at, "
                        ":visible, CAST(:payload AS JSONB), :match)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "user_id": user_id,
                        "type": tipo,
                        "occurred_at": publicado,
                        "published_at": publicado,
                        "visible": visible_to_friends,
                        "payload": json.dumps({}),
                        "match": str(uuid.uuid4()),
                    },
                )
    finally:
        await engine.dispose()


async def marcar_visto(user_id: str, visto: datetime) -> None:
    """Fija la ultima visita al feed sin pasar por el reloj."""
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE users SET feed_last_seen_at = :visto WHERE id = :id"),
                {"visto": visto, "id": user_id},
            )
    finally:
        await engine.dispose()
