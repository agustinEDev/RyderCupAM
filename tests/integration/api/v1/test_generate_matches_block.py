"""
El reintento a mano de «Generar» cuenta el motivo en claves (BE #360).

Decidido el 24 sep: claves siempre. El backend manda un código y los datos, y
la pantalla lo escribe en su idioma. Al abrir los sobres el motivo ya quedaba
así en la sesión (#364); el reintento a mano mandaba una frase en español con
los colores escritos en el servidor. Ahora apunta el motivo en la sesión, como
la apertura, y lo devuelve con un código propio.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    activate_competition,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio


async def _fourball_de_uno_contra_uno(client: AsyncClient) -> dict:
    """Una sesión de parejas con un jugador por equipo: no salen partidos."""
    creador = await create_authenticated_user(
        client, "gb_creator@test.com", "P@ssw0rd123!", "Creator", "Block"
    )
    jugadores = [
        await create_authenticated_user(
            client, f"gb_player_{i}@test.com", "P@ssw0rd123!", f"Player{i}", "Block"
        )
        for i in ("a", "b")
    ]
    admin = await create_admin_user(client, "gb_admin@test.com", "P@ssw0rd123!", "Admin", "Block")

    inicio = date.today() + timedelta(days=30)
    comp = await create_competition(
        client,
        creador["cookies"],
        {
            "name": "Generate Block Competition",
            "start_date": inicio.isoformat(),
            "end_date": (inicio + timedelta(days=3)).isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
            "visibility": "PUBLIC",
        },
    )
    comp_id = comp["id"]
    campo = await create_golf_course(client, creador["cookies"])
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/golf-courses", json={"golf_course_id": campo["id"]}
    )
    assert respuesta.status_code == 201, respuesta.text
    await activate_competition(client, creador["cookies"], comp_id)

    for jugador in jugadores:
        set_auth_cookies(client, jugador["cookies"])
        respuesta = await client.post(f"/api/v1/competitions/{comp_id}/enrollments")
        assert respuesta.status_code in (200, 201), respuesta.text
    set_auth_cookies(client, creador["cookies"])
    for inscripcion in (await client.get(f"/api/v1/competitions/{comp_id}/enrollments")).json():
        if inscripcion["status"] == "REQUESTED":
            respuesta = await client.post(f"/api/v1/enrollments/{inscripcion['id']}/approve")
            assert respuesta.status_code == 200, respuesta.text
    # Crearla ya inscribe al organizador: fuera, para quedar uno contra uno
    for inscripcion in (await client.get(f"/api/v1/competitions/{comp_id}/enrollments")).json():
        if inscripcion["user_id"] == creador["user"]["id"] and inscripcion["status"] == "APPROVED":
            respuesta = await client.post(f"/api/v1/enrollments/{inscripcion['id']}/withdraw")
            assert respuesta.status_code == 200, respuesta.text
    respuesta = await client.post(f"/api/v1/competitions/{comp_id}/close-enrollments")
    assert respuesta.status_code == 200, respuesta.text

    # La sesión antes que los equipos: así pasa a esperar partidos al repartirlos
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/rounds",
        json={
            "golf_course_id": campo["id"],
            "round_date": inicio.isoformat(),
            "session_type": "MORNING",
            "match_format": "FOURBALL",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    round_id = respuesta.json()["id"]
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/teams",
        json={
            "mode": "MANUAL",
            "team_a_player_ids": [jugadores[0]["user"]["id"]],
            "team_b_player_ids": [jugadores[1]["user"]["id"]],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return {"creador": creador, "comp_id": comp_id, "round_id": round_id}


class TestElReintentoCuentaElMotivo:
    async def test_devuelve_el_motivo_en_claves_y_lo_apunta_en_la_sesion(self, client: AsyncClient):
        """
        Given: una sesión fourball con un jugador por equipo
        When: el organizador pulsa «Generar»
        Then: 400 con el código MATCH_GENERATION_BLOCKED y el motivo en claves,
              y la agenda enseña ese mismo motivo en la sesión
        """
        montaje = await _fourball_de_uno_contra_uno(client)
        set_auth_cookies(client, montaje["creador"]["cookies"])

        respuesta = await client.post(
            f"/api/v1/competitions/rounds/{montaje['round_id']}/matches/generate", json={}
        )

        assert respuesta.status_code == 400, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == "MATCH_GENERATION_BLOCKED"
        assert cuerpo["match_generation_block"]["reason"] == "NOT_ENOUGH_PLAYERS"
        # La frase se compone en la ruta, no con el mensaje de la excepción
        assert cuerpo["detail"] == "No se pueden generar los partidos: el motivo está en la sesión"

        agenda = (await client.get(f"/api/v1/competitions/{montaje['comp_id']}/schedule")).json()
        sesiones = [r for dia in agenda["days"] for r in dia["rounds"]]
        sesion = next(r for r in sesiones if r["id"] == montaje["round_id"])
        assert sesion["status"] == "PENDING_MATCHES"
        assert sesion["match_generation_block"]["reason"] == "NOT_ENOUGH_PLAYERS"
        # El mismo motivo, con la misma hora: el guardado, no uno calculado otra vez
        assert cuerpo["match_generation_block"]["at"] is not None
        assert cuerpo["match_generation_block"] == sesion["match_generation_block"]
