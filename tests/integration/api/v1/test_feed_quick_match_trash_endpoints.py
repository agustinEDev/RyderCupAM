"""
La papelera del autor, de punta a punta (22 oct 2026): si Ana manda una partida
rapida a su papelera, su amigo Xavi deja de verla en Actividad —feed, contador
y actividad del perfil de Ana— y la vuelve a ver al sacarla. Ana sigue viendo
lo suyo, y Bea, que la jugo y no la tiene en su papelera, sigue saliendo.

Cubre el cableado real y el filtro del contador en SQL (`quick_matches`).
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.helpers.feed_helper import hacerse_amigos
from tests.integration.api.v1.test_quick_match_endpoints import _create_approved_golf_course

pytestmark = pytest.mark.asyncio

FEED = "/api/v1/users/me/feed"
CONTADOR = "/api/v1/users/me/feed/unseen-count"
PASSWORD = "P@ssw0rd123!"


async def _escena(client: AsyncClient):
    admin = await create_admin_user(client, "qmt_adm@test.com", PASSWORD, "Admin", "Papelera")
    ana = await create_authenticated_user(client, "qmt_ana@test.com", PASSWORD, "Ana", "Lopez")
    bea = await create_authenticated_user(client, "qmt_bea@test.com", PASSWORD, "Bea", "Lopez")
    xavi = await create_authenticated_user(client, "qmt_xavi@test.com", PASSWORD, "Xavi", "Lopez")
    await hacerse_amigos(client, ana, bea)
    await hacerse_amigos(client, xavi, ana)
    await hacerse_amigos(client, xavi, bea)
    campo = await _create_approved_golf_course(client, admin, ana)

    set_auth_cookies(client, ana["cookies"])
    partida = (
        await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": campo, "scoring_format": "STABLEFORD"},
        )
    ).json()["id"]
    respuesta = await client.post(
        f"/api/v1/quick-matches/{partida}/participants", json={"friend_user_id": bea["user"]["id"]}
    )
    assert respuesta.status_code == 201, respuesta.text
    respuesta = await client.post(
        f"/api/v1/quick-matches/{partida}/start", json={"scorer_ids": [ana["user"]["id"]]}
    )
    assert respuesta.status_code == 200, respuesta.text
    for hoyo in range(1, 19):
        await client.post(f"/api/v1/quick-matches/{partida}/holes/{hoyo}/score", json={"score": 4})
        respuesta = await client.post(
            f"/api/v1/quick-matches/{partida}/participants/{bea['user']['id']}/holes/{hoyo}/score",
            json={"score": 5},
        )
        assert respuesta.status_code == 200, respuesta.text
    respuesta = await client.post(f"/api/v1/quick-matches/{partida}/complete")
    assert respuesta.status_code == 200, respuesta.text
    return ana, bea, xavi, partida


async def _de_la_partida(client: AsyncClient, quien: dict, partida: str, url: str = FEED):
    """(autor, tipo) de lo que `quien` ve de la partida."""
    set_auth_cookies(client, quien["cookies"])
    respuesta = await client.get(url)
    assert respuesta.status_code == 200, respuesta.text
    return sorted(
        (e["user_id"], e["type"])
        for e in respuesta.json()["events"]
        if e["source_match_id"] == partida
    )


async def _contador(client: AsyncClient, quien: dict) -> int:
    set_auth_cookies(client, quien["cookies"])
    respuesta = await client.get(CONTADOR)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["unseen_count"]


async def _papelera(client: AsyncClient, quien: dict, partida: str, meter: bool) -> None:
    set_auth_cookies(client, quien["cookies"])
    url = f"/api/v1/quick-matches/{partida}/hide"
    respuesta = await (client.post(url) if meter else client.delete(url))
    assert respuesta.status_code == 200, respuesta.text


async def test_the_authors_trash_hides_it_from_friends_until_restored(client: AsyncClient):
    ana, bea, xavi, partida = await _escena(client)
    id_ana, id_bea = ana["user"]["id"], bea["user"]["id"]
    antes = await _de_la_partida(client, xavi, partida)
    assert {autor for autor, _ in antes} == {id_ana, id_bea}
    contador_antes = await _contador(client, xavi)
    contador_de_ana = await _contador(client, ana)
    de_ana = [fila for fila in antes if fila[0] == id_ana]
    tarjetas_de_ana = len({t for _, t in de_ana if t == "QUICK_MATCH_FINISHED"}) + (
        1 if any(t != "QUICK_MATCH_FINISHED" for _, t in de_ana) else 0
    )

    await _papelera(client, ana, partida, meter=True)

    # Xavi: nada de Ana, lo de Bea sigue
    assert {autor for autor, _ in await _de_la_partida(client, xavi, partida)} == {id_bea}
    assert await _contador(client, xavi) == contador_antes - tarjetas_de_ana
    perfil = f"/api/v1/users/{id_ana}/activity"
    assert await _de_la_partida(client, xavi, partida, perfil) == []
    # Ana sigue viendo lo suyo, en su feed y en su perfil
    assert de_ana == [f for f in await _de_la_partida(client, ana, partida) if f[0] == id_ana]
    assert await _de_la_partida(client, ana, partida, perfil) == de_ana
    assert await _contador(client, ana) == contador_de_ana

    await _papelera(client, ana, partida, meter=False)

    assert await _de_la_partida(client, xavi, partida) == antes
    assert await _contador(client, xavi) == contador_antes
    assert await _de_la_partida(client, xavi, partida, perfil) == de_ana


async def test_another_players_trash_does_not_hide_the_author(client: AsyncClient):
    ana, bea, xavi, partida = await _escena(client)
    antes = await _de_la_partida(client, xavi, partida)

    await _papelera(client, bea, partida, meter=True)

    autores = {autor for autor, _ in await _de_la_partida(client, xavi, partida)}
    assert autores == {ana["user"]["id"]}
    assert len(antes) > len(await _de_la_partida(client, xavi, partida))
