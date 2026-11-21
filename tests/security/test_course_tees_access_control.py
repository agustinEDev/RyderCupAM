"""
Security Tests - Control de acceso de lo fijado por campo (tabla del 21 nov 2026, A).

`GET /competitions/{id}/course-tees` deja ver la barra fijada por género, que el
organizador gestiona: solo él o un admin. Ni el organizador de OTRA competición
(IDOR), ni un inscrito, ni sin sesión.

OWASP: A01 (Broken Access Control)
"""

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_change_enrollment_tee_endpoint import _montar


@pytest.mark.asyncio
class TestCourseTeesAccessControl:
    """Quién lee lo fijado por campo."""

    async def test_the_organizer_of_another_competition_is_forbidden(self, client: AsyncClient):
        """
        Given dos competiciones, cada una con su organizador
        When el organizador de la segunda pide lo fijado de la primera
        Then 403
        """
        primero, _, _, _ = await _montar(client)
        segundo, _, _, _ = await _montar(client)

        set_auth_cookies(client, segundo["cookies"])
        respuesta = await client.get(
            f"/api/v1/competitions/{primero['competition_id']}/course-tees"
        )

        assert respuesta.status_code == 403, respuesta.text

    async def test_an_enrolled_player_is_forbidden(self, client: AsyncClient):
        """
        Given una jugadora inscrita
        When pide lo fijado de su competición
        Then 403
        """
        organizador, jugadora, _, _ = await _montar(client)

        set_auth_cookies(client, jugadora["cookies"])
        respuesta = await client.get(
            f"/api/v1/competitions/{organizador['competition_id']}/course-tees"
        )

        assert respuesta.status_code == 403, respuesta.text

    async def test_without_a_session_is_unauthorized(self, client: AsyncClient):
        """
        Given una competición
        When se pide lo fijado sin sesión
        Then 401
        """
        organizador, _, _, _ = await _montar(client)

        client.cookies.clear()
        respuesta = await client.get(
            f"/api/v1/competitions/{organizador['competition_id']}/course-tees"
        )

        assert respuesta.status_code == 401, respuesta.text
