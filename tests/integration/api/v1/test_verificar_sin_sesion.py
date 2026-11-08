"""
Verificar el correo ya no abre sesión (BE #753, punto 1, decidido el 7 nov).

Quien se registró con la dirección de otra persona conservaba la contraseña cuando el
dueño pulsaba el enlace: verificar le dejaba dentro, pero la cuenta seguía siendo de
quien la creó. Ahora el enlace solo verifica; se entra con la contraseña.

  V1 enlace válido, sin sesión: 200 sin cookies de sesión; la cuenta, verificada
  V2 con una sesión de esa cuenta en el navegador: no la toca y sigue valiendo
  V3 con una sesión de otra cuenta: no la toca
  V4 enlace inválido o ya usado: 400, como siempre
  (La cuenta desactivada, 403 ACCOUNT_DEACTIVATED: test_sesion_desactivada_y_codigos)
"""

import uuid

import pytest
from httpx import AsyncClient, Response

from tests.conftest import create_authenticated_user, get_user_by_email, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"
COOKIES_DE_SESION = ("access_token", "refresh_token", "csrf_token")


async def _registrado(client: AsyncClient) -> tuple[str, str]:
    email = f"v-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Lopez",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    client.cookies.clear()
    return email, (await get_user_by_email(client, email)).verification_token


def _pone_sesion(r: Response) -> list[str]:
    return [
        v.split("=", 1)[0]
        for k, v in r.headers.multi_items()
        if k == "set-cookie" and v.split("=", 1)[0] in COOKIES_DE_SESION
    ]


async def test_v1_a_valid_link_verifies_without_opening_a_session(client: AsyncClient):
    """
    Given: Una cuenta recién registrada, sin sesión en el navegador
    When: Se abre el enlace de verificación
    Then: 200, verificada, y ninguna cookie de sesión
    """
    email, token = await _registrado(client)

    r = await client.post("/api/v1/auth/verify-email", json={"token": token})

    assert r.status_code == 200, r.text
    assert r.json()["email_verified"] is True
    assert "access_token" not in r.json() and "user" not in r.json()
    assert _pone_sesion(r) == []
    assert (await get_user_by_email(client, email)).is_email_verified()


@pytest.mark.parametrize("de_quien", ["de esa cuenta", "de otra cuenta"])
async def test_v2_v3_an_open_session_is_left_alone(client: AsyncClient, de_quien):
    """
    Given: Un navegador con una sesión abierta
    When: Se abre el enlace de verificación
    Then: No se toca la sesión, que sigue valiendo
    """
    if de_quien == "de esa cuenta":
        email, token = await _registrado(client)
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
        assert r.status_code == 200, r.text
        cookies = dict(r.cookies)
    else:
        _email, token = await _registrado(client)
        otra = f"otra-{uuid.uuid4().hex[:8]}@example.com"
        cookies = (await create_authenticated_user(client, otra, CLAVE, "Bea", "Ruiz"))["cookies"]
    client.cookies.clear()
    set_auth_cookies(client, cookies)

    r = await client.post("/api/v1/auth/verify-email", json={"token": token})

    assert r.status_code == 200, r.text
    assert _pone_sesion(r) == []
    assert (await client.get("/api/v1/auth/current-user")).status_code == 200


async def test_v4_a_used_link_is_refused_as_before(client: AsyncClient):
    """
    Given: Un enlace ya usado
    When: Se abre otra vez
    Then: 400, como siempre
    """
    _email, token = await _registrado(client)
    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": token})
    ).status_code == 200

    r = await client.post("/api/v1/auth/verify-email", json={"token": token})

    assert r.status_code == 400
