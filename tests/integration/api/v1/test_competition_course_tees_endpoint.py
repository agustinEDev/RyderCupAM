"""
Lo fijado por campo, por la API (tabla del 21 nov 2026, A).

| Caso                                              | Respuesta                                |
|---------------------------------------------------|------------------------------------------|
| A1 Organizador, rojas fijadas para las mujeres    | 200 [{golf_course_id, FEMALE, RED}]      |
| A1 Admin                                          | 200, lo mismo                            |
| A2 Nada fijado                                    | 200 []                                   |
| A3 La jugadora o alguien ajeno                    | 403                                      |
| A3 Sin sesión                                     | 401                                      |
| A4 Competición que no existe                      | 404                                      |
| A5 Cancelada                                      | 200, se sigue leyendo                    |
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_admin_user, set_auth_cookies
from tests.integration.api.v1.test_change_enrollment_tee_endpoint import _montar

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _fijadas(client: AsyncClient, quien: dict | None, competicion: str):
    if quien is None:
        client.cookies.clear()
    else:
        set_auth_cookies(client, quien["cookies"])
    return await client.get(f"/api/v1/competitions/{competicion}/course-tees")


async def _con_rojas_para_ellas(client: AsyncClient):
    """La competición de `_montar`, con rojas fijadas en su campo para las mujeres."""
    organizador, jugadora, otro, inscripcion = await _montar(client)
    set_auth_cookies(client, jugadora["cookies"])
    barras = await client.get(f"/api/v1/enrollments/{inscripcion}/tees")
    campo = barras.json()["courses"][0]["golf_course_id"]
    set_auth_cookies(client, organizador["cookies"])
    fijada = await client.put(
        f"/api/v1/competitions/{organizador['competition_id']}/courses/{campo}/tee",
        json={"gender": "FEMALE", "tee_color": "RED"},
    )
    assert fijada.status_code == 200, fijada.text
    return organizador, jugadora, otro, campo


async def test_the_organizer_gets_the_course_tees(client: AsyncClient):
    """
    Given rojas fijadas en el campo para las mujeres
    When el organizador pide lo fijado
    Then 200 con esa fila
    """
    organizador, _, _, campo = await _con_rojas_para_ellas(client)

    respuesta = await _fijadas(client, organizador, organizador["competition_id"])

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == [{"golf_course_id": campo, "gender": "FEMALE", "tee_color": "RED"}]


async def test_an_admin_gets_the_course_tees(client: AsyncClient):
    """
    Given rojas fijadas en el campo para las mujeres
    When un admin que no es el organizador lo pide
    Then 200 con esa fila
    """
    organizador, _, _, campo = await _con_rojas_para_ellas(client)
    admin = await create_admin_user(
        client, f"admin-{uuid.uuid4()}@test.com", "P@ssw0rd123!", "Admin", "Fijado"
    )

    respuesta = await _fijadas(client, admin, organizador["competition_id"])

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == [{"golf_course_id": campo, "gender": "FEMALE", "tee_color": "RED"}]


async def test_nothing_set_is_an_empty_list(client: AsyncClient):
    """
    Given una competición con campo y nada fijado
    When el organizador lo pide
    Then 200 []
    """
    organizador, _, _, _ = await _montar(client)

    respuesta = await _fijadas(client, organizador, organizador["competition_id"])

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == []


@pytest.mark.parametrize("quien", ["jugadora", "otro"])
async def test_a_player_or_an_outsider_is_forbidden(client: AsyncClient, quien):
    """
    Given rojas fijadas para las mujeres
    When lo pide la jugadora inscrita o alguien ajeno
    Then 403, sin lo fijado
    """
    organizador, jugadora, otro, _ = await _con_rojas_para_ellas(client)

    respuesta = await _fijadas(
        client, {"jugadora": jugadora, "otro": otro}[quien], organizador["competition_id"]
    )

    assert respuesta.status_code == 403, respuesta.text
    assert "RED" not in respuesta.text


async def test_without_a_session_is_unauthorized(client: AsyncClient):
    """
    Given rojas fijadas para las mujeres
    When se pide sin sesión
    Then 401
    """
    organizador, _, _, _ = await _con_rojas_para_ellas(client)

    respuesta = await _fijadas(client, None, organizador["competition_id"])

    assert respuesta.status_code == 401, respuesta.text


async def test_a_missing_competition_is_not_found(client: AsyncClient):
    """
    Given una competición que no existe
    When el organizador de otra la pide
    Then 404
    """
    organizador, _, _, _ = await _montar(client)

    respuesta = await _fijadas(client, organizador, str(uuid.uuid4()))

    assert respuesta.status_code == 404, respuesta.text


async def test_a_cancelled_competition_is_still_read(client: AsyncClient):
    """
    Given rojas fijadas para las mujeres y la competición cancelada
    When el organizador lo pide
    Then 200 con esa fila
    """
    organizador, _, _, campo = await _con_rojas_para_ellas(client)
    set_auth_cookies(client, organizador["cookies"])
    cancelada = await client.post(f"/api/v1/competitions/{organizador['competition_id']}/cancel")
    assert cancelada.status_code == 200, cancelada.text

    respuesta = await _fijadas(client, organizador, organizador["competition_id"])

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == [{"golf_course_id": campo, "gender": "FEMALE", "tee_color": "RED"}]
