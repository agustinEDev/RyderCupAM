"""
Las barras por campo, por la API (20 nov 2026).

| Caso                                                   | Respuesta                                  |
|--------------------------------------------------------|--------------------------------------------|
| GET de la jugadora (campo con amarillas H y rojas M)   | 200: rojas, GENERAL, opciones [RED]        |
| GET de otro jugador                                    | 403                                        |
| PUT de su cambio propio a rojas en ese campo           | 200; el GET dice OWN                       |
| PUT de su cambio propio a azules (el campo no las tiene) | 422 TEE_NOT_AVAILABLE                    |
| PUT del organizador: rojas para las mujeres en el campo | 200; el GET dice COURSE                   |
| PUT de la jugadora a la barra del campo                | 403                                        |
"""

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_change_enrollment_tee_endpoint import _montar

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _barras(client: AsyncClient, quien: dict, inscripcion: str):
    set_auth_cookies(client, quien["cookies"])
    return await client.get(f"/api/v1/enrollments/{inscripcion}/tees")


async def _campo(client: AsyncClient, jugadora: dict, inscripcion: str) -> str:
    return (await _barras(client, jugadora, inscripcion)).json()["courses"][0]["golf_course_id"]


async def _propia(client, quien, inscripcion, campo, color):
    set_auth_cookies(client, quien["cookies"])
    return await client.put(
        f"/api/v1/enrollments/{inscripcion}/courses/{campo}/tee", json={"tee_color": color}
    )


async def test_the_player_gets_each_course_with_her_tee_and_options(client: AsyncClient):
    """
    Given una jugadora invitada en un campo con amarillas de hombre y rojas de mujer
    When pide sus barras
    Then 200: en ese campo juega rojas (las habituales), de su general, y puede
        elegir rojas; sin su género en la respuesta
    """
    _, jugadora, _, inscripcion = await _montar(client)

    respuesta = await _barras(client, jugadora, inscripcion)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["general_tee"], cuerpo["default_tee"]) == (None, "RED")
    [campo] = cuerpo["courses"]
    assert (campo["tee"], campo["source"], campo["options"]) == ("RED", "GENERAL", ["RED"])
    assert "gender" not in respuesta.text


async def test_another_player_cannot_see_them(client: AsyncClient):
    """
    Given una jugadora inscrita
    When otro jugador pide sus barras
    Then 403
    """
    _, _, otro, inscripcion = await _montar(client)

    assert (await _barras(client, otro, inscripcion)).status_code == 403


async def test_the_player_sets_her_own_course_tee(client: AsyncClient):
    """
    Given una jugadora inscrita
    When fija rojas como cambio propio en el campo
    Then 200, y el GET dice OWN
    """
    _, jugadora, _, inscripcion = await _montar(client)
    campo = await _campo(client, jugadora, inscripcion)

    respuesta = await _propia(client, jugadora, inscripcion, campo, "RED")

    assert respuesta.status_code == 200, respuesta.text
    assert (await _barras(client, jugadora, inscripcion)).json()["courses"][0]["source"] == "OWN"


async def test_a_course_tee_that_course_does_not_have_is_refused(client: AsyncClient):
    """
    Given el campo sin azules
    When la jugadora las fija como cambio propio
    Then 422 TEE_NOT_AVAILABLE
    """
    _, jugadora, _, inscripcion = await _montar(client)
    campo = await _campo(client, jugadora, inscripcion)

    respuesta = await _propia(client, jugadora, inscripcion, campo, "BLUE")

    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == "TEE_NOT_AVAILABLE"


async def test_the_organizer_sets_the_course_tee_for_women(client: AsyncClient):
    """
    Given una jugadora inscrita
    When el organizador fija rojas en el campo para las mujeres, y lo intenta ella
    Then al organizador 200 y el GET dice COURSE; a ella, 403
    """
    organizador, jugadora, _, inscripcion = await _montar(client)
    campo = await _campo(client, jugadora, inscripcion)
    ruta = f"/api/v1/competitions/{organizador['competition_id']}/courses/{campo}/tee"

    set_auth_cookies(client, jugadora["cookies"])
    suya = await client.put(ruta, json={"gender": "FEMALE", "tee_color": "RED"})
    set_auth_cookies(client, organizador["cookies"])
    del_organizador = await client.put(ruta, json={"gender": "FEMALE", "tee_color": "RED"})

    assert suya.status_code == 403, suya.text
    assert del_organizador.status_code == 200, del_organizador.text
    campo_de_ella = (await _barras(client, jugadora, inscripcion)).json()["courses"][0]
    assert campo_de_ella["source"] == "COURSE"
