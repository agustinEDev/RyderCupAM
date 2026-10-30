"""
Deshacer los equipos a mano por HTTP (decidido el 30 oct 2026).

La regla está en unitarios (test_undo_teams_use_case); aquí, los códigos de
cada respuesta, con `error_code` en la raíz para que la pantalla lo diga en su
idioma, y que después ya se puede invitar.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies
from tests.integration.api.v1.test_equipos_formados_endpoints import _con_equipos, _con_partidos

pytestmark = pytest.mark.asyncio


def _deshacer(client: AsyncClient, comp_id: str):
    return client.delete(f"/api/v1/competitions/{comp_id}/teams")


def _es(respuesta, codigo: str) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == codigo


async def test_u1_el_organizador_los_deshace_y_ya_se_invita(client: AsyncClient):
    montaje = await _con_equipos(client)
    comp_id = montaje["comp"]["id"]
    set_auth_cookies(client, montaje["creador"]["cookies"])

    deshechos = await _deshacer(client, comp_id)
    ficha = await client.get(f"/api/v1/competitions/{comp_id}")

    assert deshechos.status_code == 204, deshechos.text
    assert ficha.json()["teams_assigned"] is False
    # Los capitanes se quedan
    assert ficha.json()["team_b_captain_id"] == montaje["jugadores"][0]["user"]["id"]
    reabierta = await client.post(f"/api/v1/competitions/{comp_id}/reopen-enrollments")
    assert reabierta.status_code == 200, reabierta.text
    invitado = await create_authenticated_user(
        client, "deshacer-invitado@test.com", "P@ssw0rd123!", "Invitado", "Deshacer"
    )
    set_auth_cookies(client, montaje["creador"]["cookies"])
    invitacion = await client.post(
        f"/api/v1/competitions/{comp_id}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    assert invitacion.status_code == 201, invitacion.text


async def test_u2_con_partidos_no(client: AsyncClient):
    montaje = await _con_partidos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    _es(await _deshacer(client, montaje["comp_id"]), "TEAMS_LOCKED")


async def test_u3_sin_equipos(client: AsyncClient):
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])
    await _deshacer(client, montaje["comp"]["id"])

    _es(await _deshacer(client, montaje["comp"]["id"]), "NO_TEAMS")


async def test_u4_un_jugador_no(client: AsyncClient):
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["jugadores"][1]["cookies"])

    respuesta = await _deshacer(client, montaje["comp"]["id"])

    assert respuesta.status_code == 403, respuesta.text


async def test_u4_no_existe(client: AsyncClient):
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    respuesta = await _deshacer(client, str(uuid4()))

    assert respuesta.status_code == 404, respuesta.text
