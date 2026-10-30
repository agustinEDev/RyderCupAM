"""
Con los equipos formados, quedan así: los 409 por HTTP (decidido el 29 oct 2026).

La regla está en unitarios (test_equipos_formados_congelados); aquí, que cada
ruta da su 409 con `error_code` en la raíz, para que la pantalla lo diga en su
idioma, y que el organizador sigue pudiendo quitar a alguien y reiniciarlo.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def _con_equipos(client: AsyncClient) -> dict:
    """Una pública con el creador y tres inscritos, capitanes y equipos al azar."""
    creador = await create_authenticated_user(
        client, "congelados-org@test.com", "P@ssw0rd123!", "Org", "Congelados"
    )
    jugadores = [
        await create_authenticated_user(
            client, f"congelados-{i}@test.com", "P@ssw0rd123!", "Jugador" + "ABC"[i], "Congelados"
        )
        for i in range(3)
    ]
    comp = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, creador["cookies"])
    for jugador in jugadores:
        inscrito = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
        )
        assert inscrito.status_code == 201, inscrito.text
        jugador["enrollment_id"] = inscrito.json()["id"]
    # Nombrarlos cierra las inscripciones
    nombrados = await client.put(
        f"/api/v1/competitions/{comp['id']}/captains",
        json={
            "team_a_captain_id": creador["user"]["id"],
            "team_b_captain_id": jugadores[0]["user"]["id"],
        },
    )
    assert nombrados.status_code == 200, nombrados.text
    repartidos = await _formar(client, comp)
    assert repartidos.status_code == 201, repartidos.text
    return {"comp": comp, "creador": creador, "jugadores": jugadores}


async def _formar(client: AsyncClient, comp: dict):
    return await client.post(
        f"/api/v1/competitions/{comp['id']}/teams",
        json={"competition_id": comp["id"], "mode": "AUTOMATIC"},
    )


async def _reabrir(client: AsyncClient, montaje: dict) -> None:
    set_auth_cookies(client, montaje["creador"]["cookies"])
    reabierta = await client.post(
        f"/api/v1/competitions/{montaje['comp']['id']}/reopen-enrollments"
    )
    assert reabierta.status_code == 200, reabierta.text


def _es_teams_formed(respuesta) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "TEAMS_FORMED"


async def test_j1_el_jugador_no_se_retira(client: AsyncClient):
    montaje = await _con_equipos(client)
    jugador = montaje["jugadores"][1]
    set_auth_cookies(client, jugador["cookies"])

    baja = await client.post(f"/api/v1/enrollments/{jugador['enrollment_id']}/withdraw", json={})

    _es_teams_formed(baja)


async def test_j2_nadie_se_inscribe_en_la_publica_reabierta(client: AsyncClient):
    montaje = await _con_equipos(client)
    await _reabrir(client, montaje)
    nuevo = await create_authenticated_user(
        client, "congelados-nuevo@test.com", "P@ssw0rd123!", "Nuevo", "Congelados"
    )
    set_auth_cookies(client, nuevo["cookies"])

    pedida = await client.post(f"/api/v1/competitions/{montaje['comp']['id']}/enrollments")

    _es_teams_formed(pedida)


async def test_j4_la_invitacion_no_se_acepta(client: AsyncClient):
    montaje = await _con_equipos(client)
    await _reabrir(client, montaje)
    invitado = await create_authenticated_user(
        client, "congelados-invitado@test.com", "P@ssw0rd123!", "Invitado", "Congelados"
    )
    set_auth_cookies(client, montaje["creador"]["cookies"])
    invitacion = await client.post(
        f"/api/v1/competitions/{montaje['comp']['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert invitacion.status_code == 201, invitacion.text
    set_auth_cookies(client, invitado["cookies"])

    aceptada = await client.post(
        f"/api/v1/invitations/{invitacion.json()['id']}/respond", json={"action": "ACCEPT"}
    )

    _es_teams_formed(aceptada)


async def test_o4_no_se_vuelven_a_formar(client: AsyncClient):
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    otra_vez = await _formar(client, montaje["comp"])

    _es_teams_formed(otra_vez)


async def test_o1_el_organizador_le_quita_y_se_reinicia(client: AsyncClient):
    """Volver a formarlos tras el reinicio está en unitarios (O6): aquí quedan impares."""
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])
    quitado = montaje["jugadores"][2]

    quitar = await client.post(f"/api/v1/enrollments/{quitado['enrollment_id']}/remove")
    ficha = await client.get(f"/api/v1/competitions/{montaje['comp']['id']}")

    assert quitar.status_code == 200, quitar.text
    assert ficha.json()["teams_assigned"] is False
    # Los capitanes se quedan
    assert ficha.json()["team_b_captain_id"] == montaje["jugadores"][0]["user"]["id"]
