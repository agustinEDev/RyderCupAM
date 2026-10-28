"""
`POST /enrollments/{id}/remove`, contra Postgres (release social 2, 27 oct 2026).

El organizador quita a un inscrito: se le avisa en su Actividad, y se le puede
volver a invitar (su inscripción cerrada se reutiliza).
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def _jugador(client: AsyncClient) -> dict:
    return await create_authenticated_user(
        client, f"qui_{uuid.uuid4().hex[:6]}@test.com", "P@ssw0rd123!", "Quita", "Inscrito"
    )


async def _con_un_inscrito(client: AsyncClient):
    creador, jugador = await _jugador(client), await _jugador(client)
    start = date.today() + timedelta(days=30)
    comp = await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Quitar {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 10,
            "team_assignment": "MANUAL",
            "visibility": "PRIVATE",
        },
    )
    set_auth_cookies(client, creador["cookies"])
    dentro = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
    )
    assert dentro.status_code == 201, dentro.text
    return creador, jugador, comp, dentro.json()["id"]


async def test_el_organizador_le_quita_se_le_avisa_y_se_le_puede_reinvitar(client: AsyncClient):
    creador, jugador, comp, inscripcion = await _con_un_inscrito(client)

    set_auth_cookies(client, creador["cookies"])
    quitado = await client.post(f"/api/v1/enrollments/{inscripcion}/remove")

    assert quitado.status_code == 200, quitado.text
    assert quitado.json()["status"] == "WITHDRAWN"
    set_auth_cookies(client, jugador["cookies"])
    feed = await client.get("/api/v1/users/me/feed")
    avisos = [e for e in feed.json()["events"] if e["type"] == "ENROLLMENT_REMOVED"]
    assert len(avisos) == 1
    assert avisos[0]["payload"]["competition_id"] == comp["id"]

    set_auth_cookies(client, creador["cookies"])
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


async def test_otro_jugador_no_puede(client: AsyncClient):
    _, _, _, inscripcion = await _con_un_inscrito(client)
    otro = await _jugador(client)

    set_auth_cookies(client, otro["cookies"])
    respuesta = await client.post(f"/api/v1/enrollments/{inscripcion}/remove")

    assert respuesta.status_code == 403


async def test_el_organizador_no_se_quita_a_si_mismo_y_lo_dice_con_su_codigo(client: AsyncClient):
    creador, _, comp, _ = await _con_un_inscrito(client)
    set_auth_cookies(client, creador["cookies"])
    lista = await client.get(f"/api/v1/competitions/{comp['id']}/enrollments")
    suya = next(e for e in lista.json() if e["user_id"] == creador["user"]["id"])

    respuesta = await client.post(f"/api/v1/enrollments/{suya['id']}/remove")

    assert respuesta.status_code == 409
    assert respuesta.json()["error_code"] == "CANNOT_REMOVE_ORGANIZER"


async def test_no_existe(client: AsyncClient):
    creador, _, _, _ = await _con_un_inscrito(client)
    set_auth_cookies(client, creador["cookies"])

    respuesta = await client.post(f"/api/v1/enrollments/{uuid.uuid4()}/remove")

    assert respuesta.status_code == 404


async def test_con_equipos_y_sin_partidos_quitarle_le_saca_de_su_equipo(client: AsyncClient):
    """Contra Postgres: el reparto se queda, sin él (release social 3, 28 oct 2026)."""
    creador = await _jugador(client)
    comp = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, creador["cookies"])
    inscripciones = []
    for _ in range(3):
        jugador = await _jugador(client)
        set_auth_cookies(client, creador["cookies"])
        inscrito = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
        )
        assert inscrito.status_code == 201, inscrito.text
        inscripciones.append(inscrito.json()["id"])
    assert (
        await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
    ).status_code == 200
    reparto = await client.post(
        f"/api/v1/competitions/{comp['id']}/teams", json={"mode": "AUTOMATIC"}
    )
    assert reparto.status_code == 201, reparto.text

    quitado = await client.post(f"/api/v1/enrollments/{inscripciones[0]}/remove")

    assert quitado.status_code == 200, quitado.text
    ficha = await client.get(f"/api/v1/competitions/{comp['id']}")
    assert ficha.json()["teams_assigned"] is True
