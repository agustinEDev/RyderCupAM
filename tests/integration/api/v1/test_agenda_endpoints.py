"""
La agenda se edita desde que la competición existe, montado de verdad (BE #365).

Lo que un test unitario no ve: que las rutas dejan pasar lo que antes
rechazaban, y que los dos «no» nuevos llegan como 400 y no como 500.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import (
    _URL_DE_LA_BD_DE_TEST,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    set_auth_cookies,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _abierta_con_campo(client: AsyncClient, sufijo: str):
    """Una competición recién creada —nace con inscripciones abiertas— y su campo."""
    admin = await create_admin_user(
        client, f"agenda-admin-{sufijo}@test.com", "P@ssw0rd123!", "Admin", "Agenda"
    )
    user = await create_authenticated_user(
        client, f"agenda-{sufijo}@test.com", "P@ssw0rd123!", "Orga", "Agenda"
    )
    empieza = date.today() + timedelta(days=30)
    comp = await create_competition(
        client,
        user["cookies"],
        {
            "name": f"Agenda {uuid.uuid4().hex[:8]}",
            "start_date": empieza.isoformat(),
            "end_date": (empieza + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
        },
    )
    assert comp["status"] == "ACTIVE"
    campo = await create_golf_course(
        client,
        user["cookies"],
        golf_course_data={
            "name": f"Campo agenda {uuid.uuid4().hex[:8]}",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "location": {"latitude": 40.4168, "longitude": -3.7038},
            "tees": [
                {
                    "identifier": "Blanco",
                    "color": "WHITE",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                }
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        },
    )
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, user["cookies"])
    asociado = await client.post(
        f"/api/v1/competitions/{comp['id']}/golf-courses",
        json={"golf_course_id": campo["id"]},
    )
    assert asociado.status_code == 201, asociado.text
    return user, comp, campo, empieza


async def _configurar(client, comp_id):
    return await client.post(
        f"/api/v1/competitions/{comp_id}/schedule/configure",
        json={"mode": "AUTOMATIC", "total_sessions": 3, "sessions_per_day": 2},
    )


class TestLaAgendaDesdeElPrincipio:
    async def test_con_las_inscripciones_abiertas_se_crea_una_sesion(self, client: AsyncClient):
        _, comp, campo, empieza = await _abierta_con_campo(client, "crear")

        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/rounds",
            json={
                "golf_course_id": campo["id"],
                "round_date": empieza.isoformat(),
                "session_type": "MORNING",
                "match_format": "FOURBALL",
            },
        )

        assert respuesta.status_code == 201, respuesta.text

    async def test_y_se_propone_la_agenda_automatica(self, client: AsyncClient):
        _, comp, _, _ = await _abierta_con_campo(client, "auto")

        respuesta = await _configurar(client, comp["id"])

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["rounds_created"] == 3

    async def test_cancelada_es_un_400(self, client: AsyncClient):
        user, comp, campo, empieza = await _abierta_con_campo(client, "cancelada")
        await client.post(f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"])

        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/rounds",
            json={
                "golf_course_id": campo["id"],
                "round_date": empieza.isoformat(),
                "session_type": "MORNING",
                "match_format": "FOURBALL",
            },
        )

        assert respuesta.status_code == 400, respuesta.text

    async def test_rehacerla_con_una_sesion_con_partidos_es_un_400(self, client: AsyncClient):
        _, comp, _, _ = await _abierta_con_campo(client, "jugada")
        assert (await _configurar(client, comp["id"])).status_code == 200
        engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE rounds SET status = 'SCHEDULED' WHERE id = ("
                        "SELECT id FROM rounds WHERE competition_id = :c LIMIT 1)"
                    ),
                    {"c": comp["id"]},
                )
        finally:
            await engine.dispose()

        respuesta = await _configurar(client, comp["id"])

        assert respuesta.status_code == 400, respuesta.text
        assert "partidos" in respuesta.json()["detail"]

    async def test_con_las_inscripciones_abiertas_se_cambia_y_se_borra(self, client: AsyncClient):
        """El borrado ahora bloquea la competición: se comprueba de verdad."""
        _, comp, campo, empieza = await _abierta_con_campo(client, "borrar")
        creada = await client.post(
            f"/api/v1/competitions/{comp['id']}/rounds",
            json={
                "golf_course_id": campo["id"],
                "round_date": empieza.isoformat(),
                "session_type": "MORNING",
                "match_format": "FOURBALL",
            },
        )
        round_id = creada.json()["id"]

        cambiada = await client.put(
            f"/api/v1/competitions/rounds/{round_id}", json={"match_format": "SINGLES"}
        )
        borrada = await client.delete(f"/api/v1/competitions/rounds/{round_id}")

        assert cambiada.status_code == 200, cambiada.text
        assert borrada.status_code == 200, borrada.text
