"""
Vincular Google desde el perfil queda en el log de seguridad, con la red, y un log
roto no cambia la respuesta (revisión del registro con Google, BE #744).
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_google_oauth_service
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.shared.infrastructure.logging.security_logger import SecurityLogger
from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"


def _google(email: str) -> None:
    google = AsyncMock()
    google.exchange_code_for_user_info.return_value = GoogleUserInfo(
        google_user_id=f"google-{email}",
        email=email,
        first_name="Ana",
        last_name="Lopez",
        email_verified=True,
        picture_url=None,
    )
    app.dependency_overrides[get_google_oauth_service] = lambda: google


async def _vincula(client: AsyncClient, email: str):
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    set_auth_cookies(client, datos["cookies"])
    _google(email)
    respuesta = await client.post(
        "/api/v1/auth/google/link",
        json={"authorization_code": "code"},
        headers={"User-Agent": "Navegador de prueba"},
    )
    return datos, respuesta


async def test_linking_google_from_the_profile_is_logged_with_the_network(
    client: AsyncClient, monkeypatch
):
    """
    Given: Un usuario con sesión
    When: Vincula Google desde su perfil
    Then: 200, y el log apunta un vínculo manual con su navegador y una IP
    """
    apuntes = []
    monkeypatch.setattr(
        SecurityLogger, "log_google_account_linked", lambda self, **kw: apuntes.append(kw)
    )

    datos, respuesta = await _vincula(client, "vinculo.log@example.com")

    assert respuesta.status_code == 200
    assert len(apuntes) == 1
    assert apuntes[0]["user_id"] == datos["user"]["id"]
    assert apuntes[0]["automatic"] is False
    assert apuntes[0]["user_agent"] == "Navegador de prueba"
    assert apuntes[0]["ip_address"]


async def test_a_broken_log_does_not_change_the_link_answer(client: AsyncClient, monkeypatch):
    """
    Given: El log de seguridad falla
    When: Vincula Google desde su perfil
    Then: 200 igual: el vínculo ya está guardado y el log nunca cambia la respuesta
    """

    def roto(self, **kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(SecurityLogger, "log_google_account_linked", roto)

    _datos, respuesta = await _vincula(client, "vinculo.roto@example.com")

    assert respuesta.status_code == 200
