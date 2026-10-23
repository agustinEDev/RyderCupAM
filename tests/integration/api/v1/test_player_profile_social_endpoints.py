"""
El perfil de otro jugador de punta a punta (BE-3, tabla aprobada el 22 oct 2026).

| Caso                                                    | Resultado                            |
|---------------------------------------------------------|--------------------------------------|
| 1 No amigo con hándicap                                 | Lo ve; cara a cara y partidas, null  |
| 3 Bloqueado                                             | Sin hándicap                         |
| 4 Amigo con un singles rápido jugado                    | Cara a cara y la partida en la lista |
| 6 Uno mismo                                             | Sin cara a cara ni partidas          |
| 11 «Ver más» de un amigo                                | 200 con la partida                   |
| 17 «Ver más» sin ser amigo / sin sesión / no existe     | 403 / 401 / 404                      |
| 19 Una partida o tres                                   | Las mismas consultas                 |
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_golf_course,
    set_auth_cookies,
)
from tests.integration.api.v1.helpers.feed_helper import hacerse_amigos

PASSWORD = "P@ssw0rd123!"


async def _usuario(client: AsyncClient, email: str, nombre: str) -> dict:
    """Con hándicap: sin él, una partida con hándicap no se juzga en el cara a cara."""
    usuario = await create_authenticated_user(client, email, PASSWORD, nombre, "Golfista")
    set_auth_cookies(client, usuario["cookies"])
    puesto = await client.post(
        "/api/v1/handicaps/update-manual",
        json={"user_id": usuario["user"]["id"], "handicap": 10.0},
    )
    assert puesto.status_code == 200, puesto.text
    return usuario


async def _campo(client: AsyncClient, prefijo: str, creador: dict) -> str:
    admin = await create_admin_user(client, f"{prefijo}_admin@test.com", PASSWORD, "Admin", "Campo")
    course = await create_golf_course(client, creador["cookies"])
    await approve_golf_course(client, admin["cookies"], course["id"])
    return course["id"]


async def _singles(
    client: AsyncClient, course_id: str, yo: dict, el: dict, mio: int, suyo: int, hoyos: int = 9
) -> str:
    """
    Un singles rapido de `hoyos` hoyos (9 por defecto, lo minimo que cuenta
    desde la tabla del 22 oct), anotado por cada uno y terminado.
    """
    set_auth_cookies(client, yo["cookies"])
    creada = await client.post(
        "/api/v1/quick-matches", json={"golf_course_id": course_id, "match_format": "SINGLES"}
    )
    assert creada.status_code == 201, creada.text
    match_id = creada.json()["id"]
    anadido = await client.post(
        f"/api/v1/quick-matches/{match_id}/participants",
        json={"friend_user_id": el["user"]["id"]},
    )
    assert anadido.status_code == 201, anadido.text
    empezada = await client.post(
        f"/api/v1/quick-matches/{match_id}/start",
        json={"scorer_ids": [yo["user"]["id"], el["user"]["id"]]},
    )
    assert empezada.status_code == 200, empezada.text
    for hoyo in range(1, hoyos + 1):
        set_auth_cookies(client, yo["cookies"])
        anotado = await client.post(
            f"/api/v1/quick-matches/{match_id}/holes/{hoyo}/score", json={"score": mio}
        )
        assert anotado.status_code == 200, anotado.text
        set_auth_cookies(client, el["cookies"])
        anotado = await client.post(
            f"/api/v1/quick-matches/{match_id}/holes/{hoyo}/score", json={"score": suyo}
        )
        assert anotado.status_code == 200, anotado.text
    set_auth_cookies(client, yo["cookies"])
    terminada = await client.post(f"/api/v1/quick-matches/{match_id}/complete")
    assert terminada.status_code == 200, terminada.text
    return match_id


async def _perfil(client: AsyncClient, quien: dict, de: dict) -> dict:
    set_auth_cookies(client, quien["cookies"])
    respuesta = await client.get(f"/api/v1/users/{de['user']['id']}/profile")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


@pytest.mark.asyncio
class TestPerfilSocial:
    async def test_un_no_amigo_ve_el_handicap_y_nada_de_lo_jugado(self, client: AsyncClient):
        """Caso 1."""
        yo = await _usuario(client, "ps_a1@test.com", "Ana")
        el = await _usuario(client, "ps_a2@test.com", "Luis")
        set_auth_cookies(client, el["cookies"])
        puesto = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": el["user"]["id"], "handicap": 14.2},
        )
        assert puesto.status_code == 200, puesto.text

        datos = await _perfil(client, yo, el)

        assert abs(datos["handicap"] - 14.2) < 0.01
        assert datos["stats"] is None
        assert datos["head_to_head"] is None
        assert datos["games_together"] is None

    async def test_bloqueado_no_ve_el_handicap(self, client: AsyncClient):
        """Caso 3: solo nombre y foto; el número de amigos llega a 0."""
        yo = await _usuario(client, "ps_b1@test.com", "Ana")
        el = await _usuario(client, "ps_b2@test.com", "Luis")
        await hacerse_amigos(client, el, await _usuario(client, "ps_b3@test.com", "Eva"))
        set_auth_cookies(client, el["cookies"])
        await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": el["user"]["id"], "handicap": 14.2},
        )
        set_auth_cookies(client, el["cookies"])
        bloqueo = await client.post(f"/api/v1/friends/{yo['user']['id']}/block")
        assert bloqueo.status_code in (200, 201), bloqueo.text

        datos = await _perfil(client, yo, el)

        assert datos["friendship"]["status"] == "BLOCKED"
        assert datos["handicap"] is None
        assert datos["friends_count"] == 0
        # F (22 oct): me bloqueo el; desde su lado, lo bloqueo el
        assert datos["blocked_by_me"] is False
        assert (await _perfil(client, el, yo))["blocked_by_me"] is True

    async def test_un_amigo_ve_el_cara_a_cara_y_las_partidas_juntos(self, client: AsyncClient):
        """Caso 4: gano el singles (4 contra 5, scratch en un hoyo)."""
        yo = await _usuario(client, "ps_c1@test.com", "Ana")
        el = await _usuario(client, "ps_c2@test.com", "Luis")
        await hacerse_amigos(client, yo, el)
        course_id = await _campo(client, "ps_c", yo)
        match_id = await _singles(client, course_id, yo, el, mio=4, suyo=5)

        datos = await _perfil(client, yo, el)

        assert datos["head_to_head"] == {
            "against": {"won": 1, "halved": 0, "lost": 0},
            "alongside": None,
        }
        (partida,) = datos["games_together"]["games"]
        assert partida["kind"] == "QUICK_MATCH"
        assert partida["quick_match_id"] == match_id
        assert partida["format"] == "SINGLES"
        assert partida["relation"] == "AGAINST"
        assert partida["result"] == "WON"
        assert datos["games_together"]["next_cursor"] is None

        # Y desde su lado, la perdio
        suyos = await _perfil(client, el, yo)
        assert suyos["head_to_head"]["against"] == {"won": 0, "halved": 0, "lost": 1}

    async def test_con_un_solo_hoyo_sale_sin_terminar_y_no_cuenta(self, client: AsyncClient):
        """Tabla del 22 oct, A: un hoyo anotado ya no es «Ganaste 1UP»."""
        yo = await _usuario(client, "ps_u1@test.com", "Ana")
        el = await _usuario(client, "ps_u2@test.com", "Luis")
        await hacerse_amigos(client, yo, el)
        course_id = await _campo(client, "ps_u", yo)
        await _singles(client, course_id, yo, el, mio=4, suyo=5, hoyos=1)

        datos = await _perfil(client, yo, el)

        assert datos["head_to_head"] is None
        (partida,) = datos["games_together"]["games"]
        assert partida["result"] == "UNFINISHED"

    async def test_uno_mismo_no_tiene_cara_a_cara(self, client: AsyncClient):
        """Caso 6."""
        yo = await _usuario(client, "ps_d1@test.com", "Ana")

        datos = await _perfil(client, yo, yo)

        assert datos["head_to_head"] is None
        assert datos["games_together"] is None


@pytest.mark.asyncio
class TestVerMasPartidasJuntos:
    async def test_un_amigo_las_ve(self, client: AsyncClient):
        """Caso 11."""
        yo = await _usuario(client, "ps_e1@test.com", "Ana")
        el = await _usuario(client, "ps_e2@test.com", "Luis")
        await hacerse_amigos(client, yo, el)
        course_id = await _campo(client, "ps_e", yo)
        match_id = await _singles(client, course_id, yo, el, mio=5, suyo=4)

        set_auth_cookies(client, yo["cookies"])
        respuesta = await client.get(f"/api/v1/users/{el['user']['id']}/games-together")

        assert respuesta.status_code == 200, respuesta.text
        (partida,) = respuesta.json()["games"]
        assert (partida["id"], partida["result"]) == (match_id, "LOST")

    async def test_quien_no_es_amigo_recibe_403(self, client: AsyncClient):
        """Caso 17."""
        yo = await _usuario(client, "ps_f1@test.com", "Ana")
        el = await _usuario(client, "ps_f2@test.com", "Luis")

        set_auth_cookies(client, yo["cookies"])
        respuesta = await client.get(f"/api/v1/users/{el['user']['id']}/games-together")

        assert respuesta.status_code == 403

    async def test_sin_sesion_401(self, client: AsyncClient):
        """Caso 17."""
        el = await _usuario(client, "ps_g1@test.com", "Luis")

        client.cookies.clear()
        respuesta = await client.get(f"/api/v1/users/{el['user']['id']}/games-together")

        assert respuesta.status_code == 401

    async def test_una_cuenta_que_no_existe_404(self, client: AsyncClient):
        yo = await _usuario(client, "ps_h1@test.com", "Ana")

        set_auth_cookies(client, yo["cookies"])
        respuesta = await client.get(f"/api/v1/users/{uuid.uuid4()}/games-together")

        assert respuesta.status_code == 404


async def _sentencias_de_lo_jugado(client: AsyncClient, yo: dict, el: dict) -> int:
    sentencias: list[str] = []

    def _cuenta(conn, cursor, statement, *args):
        sentencias.append(statement)

    set_auth_cookies(client, yo["cookies"])
    event.listen(Engine, "before_cursor_execute", _cuenta)
    try:
        respuesta = await client.get(f"/api/v1/users/{el['user']['id']}/games-together")
    finally:
        event.remove(Engine, "before_cursor_execute", _cuenta)
    assert respuesta.status_code == 200
    return len(sentencias)


@pytest.mark.asyncio
async def test_caso_19_las_mismas_consultas_con_una_partida_que_con_tres(client: AsyncClient):
    """
    Caso 19. Given dos amigos con una partida y otros dos con tres / When se
    piden las partidas juntos / Then cuesta las mismas consultas: nada se pide
    partida a partida.

    Se mide el «ver mas» y no el perfil entero porque el perfil incluye las
    estadisticas del amigo, que hoy leen los golpes partida a partida (fuera de
    esta tarea): el cara a cara del perfil sale de la misma lectura que esto.
    """
    a1 = await _usuario(client, "ps_q1@test.com", "Ana")
    b1 = await _usuario(client, "ps_q2@test.com", "Luis")
    await hacerse_amigos(client, a1, b1)
    # Tres campos distintos: con uno solo, cargarlos de uno en uno no se notaria
    campos = [await _campo(client, f"ps_q{i}", a1) for i in range(3)]
    await _singles(client, campos[0], a1, b1, mio=4, suyo=5)

    a3 = await _usuario(client, "ps_q3@test.com", "Eva")
    b3 = await _usuario(client, "ps_q4@test.com", "Juan")
    await hacerse_amigos(client, a3, b3)
    for course_id, (mio, suyo) in zip(campos, ((4, 5), (5, 4), (4, 4)), strict=True):
        await _singles(client, course_id, a3, b3, mio=mio, suyo=suyo)

    una = await _sentencias_de_lo_jugado(client, a1, b1)
    tres = await _sentencias_de_lo_jugado(client, a3, b3)

    assert tres == una
