"""
Volver a entrar con una inscripción vieja, contra Postgres (release social 2, 27 oct 2026).

La restricción única (competición, usuario) no mira el estado: el arreglo
reutiliza la fila cerrada, y aquí se ve que la base de datos lo acepta.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def _jugador(client: AsyncClient) -> dict:
    nombre = uuid.uuid4().hex[:6]
    return await create_authenticated_user(
        client, f"vae_{nombre}@test.com", "P@ssw0rd123!", "Vuelve", "Entrar"
    )


async def _publica(client: AsyncClient, creador: dict) -> dict:
    start = date.today() + timedelta(days=30)
    return await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Vuelve {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 10,
            "team_assignment": "MANUAL",
            "visibility": "PUBLIC",
        },
    )


async def _pide(client: AsyncClient, jugador: dict, comp: dict):
    set_auth_cookies(client, jugador["cookies"])
    return await client.post(f"/api/v1/competitions/{comp['id']}/enrollments", json={})


async def test_rechazada_vuelve_a_pedir_y_luego_acepta_una_invitacion(client: AsyncClient):
    creador, jugador = await _jugador(client), await _jugador(client)
    comp = await _publica(client, creador)
    pedida = await _pide(client, jugador, comp)
    assert pedida.status_code == 201, pedida.text
    set_auth_cookies(client, creador["cookies"])
    assert (
        await client.post(f"/api/v1/enrollments/{pedida.json()['id']}/reject")
    ).status_code == 200

    # V2: pide otra vez, con la misma fila
    otra = await _pide(client, jugador, comp)
    assert otra.status_code == 201, otra.text
    assert otra.json()["id"] == pedida.json()["id"]
    assert otra.json()["status"] == "REQUESTED"

    # Se la vuelven a rechazar, y le invitan: V1, entra
    set_auth_cookies(client, creador["cookies"])
    assert (await client.post(f"/api/v1/enrollments/{otra.json()['id']}/reject")).status_code == 200
    invitacion = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": jugador["user"]["id"]},
    )
    assert invitacion.status_code == 201, invitacion.text
    set_auth_cookies(client, jugador["cookies"])
    aceptada = await client.post(
        f"/api/v1/invitations/{invitacion.json()['id']}/respond", json={"action": "ACCEPT"}
    )

    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["enrollment_id"] == pedida.json()["id"]


async def test_retirado_vuelve_a_mano_del_organizador(client: AsyncClient):
    creador, jugador = await _jugador(client), await _jugador(client)
    comp = await _publica(client, creador)
    set_auth_cookies(client, creador["cookies"])
    dentro = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
    )
    assert dentro.status_code == 201, dentro.text
    set_auth_cookies(client, jugador["cookies"])
    assert (
        await client.post(f"/api/v1/enrollments/{dentro.json()['id']}/withdraw", json={})
    ).status_code == 200

    # V3
    set_auth_cookies(client, creador["cookies"])
    otra_vez = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
    )

    assert otra_vez.status_code == 201, otra_vez.text
    assert otra_vez.json()["id"] == dentro.json()["id"]
    assert otra_vez.json()["status"] == "APPROVED"
