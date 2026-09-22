"""
La sala de draft por HTTP y contra Postgres (FE #653).

Lo que un test en memoria no ve: que las tres rutas están montadas, que el
CSRF y la sesión dejan pasar, que las elecciones sobreviven a la base de datos
y que al terminar la sala los equipos quedan de verdad repartidos —que es lo
que leen las rondas y los partidos—.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)

pytestmark = [pytest.mark.asyncio]


async def _cerrada_con_capitanes(client: AsyncClient, jugadores: int = 5) -> dict:
    """Una competición cerrada, con sus dos capitanes y `jugadores` inscritos.

    Devuelve el organizador, los dos capitanes, el resto y la competición.
    """
    creador = await create_authenticated_user(
        client, "draft-org@test.com", "P@ssw0rd123!", "Org", "Draft"
    )
    resto = [
        await create_authenticated_user(
            client, f"draft-{i}@test.com", "P@ssw0rd123!", "Jugador" + "ABCDEFGH"[i], "Draft"
        )
        for i in range(jugadores - 1)
    ]
    comp = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, creador["cookies"])
    for jugador in resto:
        inscrito = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
        )
        assert inscrito.status_code == 201, inscrito.text

    capitan_a, capitan_b = creador, resto[0]
    nombrados = await client.put(
        f"/api/v1/competitions/{comp['id']}/captains",
        json={
            "team_a_captain_id": capitan_a["user"]["id"],
            "team_b_captain_id": capitan_b["user"]["id"],
        },
    )
    assert nombrados.status_code == 200, nombrados.text
    return {
        "comp": comp,
        "creador": creador,
        "capitanes": {"A": capitan_a, "B": capitan_b},
        "resto": resto[1:],
    }


async def _elegir(client: AsyncClient, sala: dict, comp_id: str, jugador_id: str):
    """Elige con las cookies del capitán al que le toca."""
    set_auth_cookies(client, sala["capitanes"][sala["estado"]["current_team"]]["cookies"])
    return await client.post(
        f"/api/v1/competitions/{comp_id}/draft/picks", json={"player_id": jugador_id}
    )


class TestLaSalaPorHttp:
    async def test_el_organizador_la_abre_y_cualquiera_la_mira(self, client: AsyncClient):
        """
        Given: una cerrada con sus capitanes
        When: el organizador lanza el sorteo y otro inscrito mira la sala
        Then: los dos ven el mismo turno, y los elegibles llevan nombre y hándicap
        """
        montaje = await _cerrada_con_capitanes(client)
        comp_id = montaje["comp"]["id"]

        set_auth_cookies(client, montaje["creador"]["cookies"])
        abierta = await client.post(f"/api/v1/competitions/{comp_id}/draft")

        set_auth_cookies(client, montaje["resto"][0]["cookies"])
        mirada = await client.get(f"/api/v1/competitions/{comp_id}/draft")

        assert abierta.status_code == 201, abierta.text
        sala = abierta.json()
        assert sala["status"] == "IN_PROGRESS"
        assert sala["current_team"] in ("A", "B")
        assert sala["server_time"] is not None
        # Tres elegibles: cinco inscritos menos los dos capitanes
        assert len(sala["available_players"]) == 3
        assert all(j["name"] and j["handicap"] is not None for j in sala["available_players"])
        assert mirada.status_code == 200
        assert mirada.json()["current_team"] == sala["current_team"]

    async def test_sin_sorteo_todavia_no_hay_sala(self, client: AsyncClient):
        montaje = await _cerrada_con_capitanes(client)

        set_auth_cookies(client, montaje["creador"]["cookies"])
        mirada = await client.get(f"/api/v1/competitions/{montaje['comp']['id']}/draft")

        assert mirada.status_code == 404

    async def test_otro_jugador_no_lanza_el_sorteo(self, client: AsyncClient):
        montaje = await _cerrada_con_capitanes(client)

        set_auth_cookies(client, montaje["resto"][0]["cookies"])
        abierta = await client.post(f"/api/v1/competitions/{montaje['comp']['id']}/draft")

        assert abierta.status_code == 403

    async def test_el_capitan_que_no_es_de_turno_recibe_409(self, client: AsyncClient):
        """409 y no 403: no es que no pueda elegir nunca, es que ahora no le toca."""
        montaje = await _cerrada_con_capitanes(client)
        comp_id = montaje["comp"]["id"]
        set_auth_cookies(client, montaje["creador"]["cookies"])
        sala = (await client.post(f"/api/v1/competitions/{comp_id}/draft")).json()

        el_otro = "B" if sala["current_team"] == "A" else "A"
        set_auth_cookies(client, montaje["capitanes"][el_otro]["cookies"])
        elegido = await client.post(
            f"/api/v1/competitions/{comp_id}/draft/picks",
            json={"player_id": sala["available_players"][0]["user_id"]},
        )

        assert elegido.status_code == 409, elegido.text

    async def test_al_elegir_a_todos_los_equipos_quedan_repartidos(self, client: AsyncClient):
        """
        Given: la sala abierta
        When: los capitanes eligen por turnos hasta que no queda nadie
        Then: la sala termina y la agenda ya tiene los equipos, con cada capitán
              encabezando el suyo
        """
        montaje = await _cerrada_con_capitanes(client)
        comp_id = montaje["comp"]["id"]
        set_auth_cookies(client, montaje["creador"]["cookies"])
        montaje["estado"] = (await client.post(f"/api/v1/competitions/{comp_id}/draft")).json()

        while montaje["estado"]["status"] == "IN_PROGRESS":
            siguiente = montaje["estado"]["available_players"][0]["user_id"]
            respuesta = await _elegir(client, montaje, comp_id, siguiente)
            assert respuesta.status_code == 201, respuesta.text
            montaje["estado"] = respuesta.json()

        sala = montaje["estado"]
        assert sala["status"] == "COMPLETED"
        assert sala["current_team"] is None
        assert len(sala["picks"]) == 3
        assert sala["team_a"][0] == montaje["capitanes"]["A"]["user"]["id"]
        assert sala["team_b"][0] == montaje["capitanes"]["B"]["user"]["id"]

        set_auth_cookies(client, montaje["creador"]["cookies"])
        agenda = await client.get(f"/api/v1/competitions/{comp_id}/schedule")
        assert agenda.status_code == 200
        reparto = agenda.json()["team_assignment"]
        assert sorted(reparto["team_a_player_ids"]) == sorted(sala["team_a"])
        assert sorted(reparto["team_b_player_ids"]) == sorted(sala["team_b"])

    async def test_el_reparto_por_api_no_acepta_el_modo_draft(self, client: AsyncClient):
        """Un reparto calculado por la aplicación no puede decir que lo eligieron
        los capitanes, y además bloquearía la sala: con equipos hechos ya no se abre."""
        # Seis, que con un número impar el reparto se queja de eso primero
        montaje = await _cerrada_con_capitanes(client, jugadores=6)
        set_auth_cookies(client, montaje["creador"]["cookies"])

        repartido = await client.post(
            f"/api/v1/competitions/{montaje['comp']['id']}/teams",
            json={"competition_id": montaje["comp"]["id"], "mode": "DRAFT"},
        )

        assert repartido.status_code == 400, repartido.text
        assert "draft" in repartido.json()["detail"].lower()

    async def test_con_los_equipos_hechos_no_se_vuelve_a_sortear(self, client: AsyncClient):
        """Un draft sobre equipos ya hechos los reharía por detrás."""
        montaje = await _cerrada_con_capitanes(client)
        comp_id = montaje["comp"]["id"]
        set_auth_cookies(client, montaje["creador"]["cookies"])
        montaje["estado"] = (await client.post(f"/api/v1/competitions/{comp_id}/draft")).json()
        while montaje["estado"]["status"] == "IN_PROGRESS":
            respuesta = await _elegir(
                client, montaje, comp_id, montaje["estado"]["available_players"][0]["user_id"]
            )
            montaje["estado"] = respuesta.json()

        set_auth_cookies(client, montaje["creador"]["cookies"])
        otra_vez = await client.post(f"/api/v1/competitions/{comp_id}/draft")

        assert otra_vez.status_code == 400, otra_vez.text
