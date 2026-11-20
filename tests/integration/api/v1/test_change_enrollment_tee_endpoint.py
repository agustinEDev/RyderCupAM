"""
Cambiar las barras de una inscripción por la API (BE #912, 20 nov 2026).

| Caso                                                   | Respuesta                        |
|--------------------------------------------------------|----------------------------------|
| La jugadora, rojas de mujer que el campo tiene          | 200 con RED                      |
| La jugadora, azules que el campo no tiene para mujer    | 422 TEE_NOT_AVAILABLE            |
| Otro jugador                                           | 403                              |
| El organizador vuelve a las de por defecto (null)      | 200 sin barras                   |
| Un color que no existe                                 | 422 de validación                |
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    inscrito_por_invitacion,
    set_auth_cookies,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

BARRAS = [
    {
        "identifier": "Amarillo",
        "color": "YELLOW",
        "tee_gender": "MALE",
        "course_rating": 70.2,
        "slope_rating": 128,
        "par": 72,
    },
    {
        "identifier": "Rojo",
        "color": "RED",
        "tee_gender": "FEMALE",
        "course_rating": 71.0,
        "slope_rating": 124,
        "par": 72,
    },
]


async def _usuario(client: AsyncClient, gender: str) -> dict:
    return await create_authenticated_user(
        client,
        f"barras-{uuid.uuid4().hex[:8]}@test.com",
        "P@ssw0rd123!",
        "Bea",
        "Rras",
        gender=gender,
    )


async def _montar(client: AsyncClient) -> tuple[dict, dict, dict, str]:
    """Una competición con un campo de amarillas de hombre y rojas de mujer, y una invitada."""
    organizador = await _usuario(client, "MALE")
    jugadora = await _usuario(client, "FEMALE")
    otro = await _usuario(client, "MALE")
    competicion = await create_competition(client, organizador["cookies"])
    admin = await create_admin_user(
        client, f"admin-{uuid.uuid4()}@test.com", "P@ssw0rd123!", "Admin", "Barras"
    )
    campo = await create_golf_course(
        client,
        organizador["cookies"],
        {
            "name": f"Campo barras {uuid.uuid4().hex[:8]}",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": BARRAS,
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        },
    )
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, organizador["cookies"])
    anadido = await client.post(
        f"/api/v1/competitions/{competicion['id']}/golf-courses",
        json={"golf_course_id": campo["id"]},
    )
    assert anadido.status_code == 201, anadido.text
    aceptada = await inscrito_por_invitacion(
        client, organizador["cookies"], competicion["id"], jugadora
    )
    return organizador, jugadora, otro, aceptada["enrollment_id"]


async def _cambiar(client: AsyncClient, quien: dict, inscripcion: str, color):
    set_auth_cookies(client, quien["cookies"])
    return await client.put(f"/api/v1/enrollments/{inscripcion}/tee", json={"tee_color": color})


async def test_the_player_changes_to_a_rated_tee(client: AsyncClient):
    _, jugadora, _, inscripcion = await _montar(client)

    respuesta = await _cambiar(client, jugadora, inscripcion, "RED")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["tee_color"] == "RED"


async def test_a_tee_not_rated_for_her_is_refused_with_its_code(client: AsyncClient):
    _, jugadora, _, inscripcion = await _montar(client)

    respuesta = await _cambiar(client, jugadora, inscripcion, "BLUE")

    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == "TEE_NOT_AVAILABLE"


async def test_another_player_cannot_change_it(client: AsyncClient):
    _, _, otro, inscripcion = await _montar(client)

    respuesta = await _cambiar(client, otro, inscripcion, "RED")

    assert respuesta.status_code == 403, respuesta.text


async def test_the_organizer_goes_back_to_the_default(client: AsyncClient):
    organizador, jugadora, _, inscripcion = await _montar(client)
    await _cambiar(client, jugadora, inscripcion, "RED")

    respuesta = await _cambiar(client, organizador, inscripcion, None)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["tee_color"] is None


async def test_an_unknown_colour_is_a_validation_error(client: AsyncClient):
    _, jugadora, _, inscripcion = await _montar(client)

    respuesta = await _cambiar(client, jugadora, inscripcion, "PURPLE")

    assert respuesta.status_code == 422, respuesta.text
