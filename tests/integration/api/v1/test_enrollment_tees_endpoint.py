"""
Las barras que se pueden elegir para una inscripción, por la API (BE #912).

| Caso                                   | Respuesta                                     |
|----------------------------------------|-----------------------------------------------|
| La jugadora, campo de amarillas H y rojas M | 200: tees [RED], default RED, current null |
| Tras elegir rojas                      | current RED                                   |
| El organizador                         | lo mismo que ella                             |
| Otro jugador                           | 403                                           |
"""

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_change_enrollment_tee_endpoint import _cambiar, _montar

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _barras(client: AsyncClient, quien: dict, inscripcion: str):
    set_auth_cookies(client, quien["cookies"])
    return await client.get(f"/api/v1/enrollments/{inscripcion}/tees")


async def test_the_player_gets_her_rated_tees_and_her_default(client: AsyncClient):
    """
    Given una jugadora invitada en un campo con amarillas de hombre y rojas de mujer
    When pide sus barras
    Then 200 con rojas, rojas por defecto y sin elegir; sin su género
    """
    _, jugadora, _, inscripcion = await _montar(client)

    respuesta = await _barras(client, jugadora, inscripcion)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"tees": ["RED"], "default_tee": "RED", "current_tee": None}


async def test_after_choosing_the_current_tee_shows(client: AsyncClient):
    """
    Given una jugadora que eligió rojas
    When pide sus barras
    Then la actual es RED
    """
    _, jugadora, _, inscripcion = await _montar(client)
    elegida = await _cambiar(client, jugadora, inscripcion, "RED")
    assert elegida.status_code == 200, elegida.text

    respuesta = await _barras(client, jugadora, inscripcion)

    assert respuesta.json()["current_tee"] == "RED"


async def test_the_organizer_gets_the_same_tees(client: AsyncClient):
    """
    Given una jugadora inscrita
    When el organizador pide sus barras
    Then le salen las de ella, aunque el front no sepa su género
    """
    organizador, _, _, inscripcion = await _montar(client)

    respuesta = await _barras(client, organizador, inscripcion)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["tees"] == ["RED"]


async def test_another_player_cannot_see_them(client: AsyncClient):
    """
    Given una jugadora inscrita
    When otro jugador pide sus barras
    Then 403
    """
    _, _, otro, inscripcion = await _montar(client)

    respuesta = await _barras(client, otro, inscripcion)

    assert respuesta.status_code == 403, respuesta.text
