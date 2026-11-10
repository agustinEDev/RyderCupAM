"""
PKCE en el login y en vincular Google, por la API (FE-02, fase 3 del plan a 9).

El `code_verifier` del cuerpo, OPCIONAL en esta release (obligatorio en la 3), llega
al canje del código; sin él, como hoy; mal formado, 422 sin gastar el código.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_google_oauth_service
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CLAVE = "V@l1dP@ss123!"


@pytest.fixture(autouse=True)
def sin_google_de_verdad():
    yield
    app.dependency_overrides.pop(get_google_oauth_service, None)


def _google(email: str) -> AsyncMock:
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
    return google


async def _login(client: AsyncClient, **cuerpo):
    return await client.post(
        "/api/v1/auth/google",
        json={"authorization_code": "code", **cuerpo},
        headers={"X-Test-Client-ID": "pkce"},
    )


@pytest.mark.parametrize("con_verifier", [False, True], ids=["sin", "con"])
async def test_login_pasa_el_verifier_al_canje(client: AsyncClient, con_verifier: bool):
    """
    Given: Un login con Google, con o sin code_verifier
    When: Se canjea el código
    Then: Entra, y el canje recibe el verifier (o None sin él)
    """
    google = _google(f"pkce-login-{con_verifier}@gmail.com")
    cuerpo = {"code_verifier": VERIFIER} if con_verifier else {}

    r = await _login(client, **cuerpo)

    assert r.status_code == 200, r.text
    google.exchange_code_for_user_info.assert_awaited_once_with(
        "code", code_verifier=VERIFIER if con_verifier else None
    )


async def test_login_con_un_verifier_mal_formado_da_422_sin_canjear(client: AsyncClient):
    """
    Given: Un login con un code_verifier demasiado corto
    When: Llega a la API
    Then: 422, y el código de Google no se gasta
    """
    google = _google("pkce-malo@gmail.com")

    r = await _login(client, code_verifier="corto")

    assert r.status_code == 422
    google.exchange_code_for_user_info.assert_not_awaited()


async def test_vincular_pasa_el_verifier_al_canje(client: AsyncClient):
    """
    Given: Una cuenta verificada que acaba de escribir su contraseña
    When: Vincula Google con code_verifier
    Then: 200, y el canje recibe el verifier
    """
    email = "pkce-vincula@example.com"
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await sql_en_la_bd_de_test("update users set email_verified = true where email = :e", e=email)
    google = _google(email)
    set_auth_cookies(client, datos["cookies"])
    csrf = {"X-CSRF-Token": client.cookies.get("csrf_token", "")}
    r = await client.post("/api/v1/auth/reauthenticate", json={"password": CLAVE}, headers=csrf)
    assert r.status_code == 200, r.text

    r = await client.post(
        "/api/v1/auth/google/link",
        json={"authorization_code": "code", "code_verifier": VERIFIER},
        headers=csrf,
    )

    assert r.status_code == 200, r.text
    google.exchange_code_for_user_info.assert_awaited_once_with("code", code_verifier=VERIFIER)
