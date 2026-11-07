"""
El límite de `PATCH /users/security` (BE #753, punto 5, decidido el 7 nov).

Cada petición que pide un correo nuevo manda dos correos, uno a cualquier dirección,
del cupo compartido de 100 al día. Y cada una prueba una contraseña.

  L1 todo el endpoint: 10 por hora y usuario; la 11.ª, 429 TOO_MANY_SECURITY_CHANGES
  L2 con `new_email`, además 3 por hora; la 4.ª, 429 TOO_MANY_EMAIL_CHANGE_REQUESTS
  L3 cambiar solo la contraseña no gasta el cupo del correo
  L4 cada usuario tiene su contador
  L5 el 429 lleva un texto fijo, sin el límite ni la clave
"""

import uuid

import pytest
from httpx import AsyncClient, Response

from src.config.rate_limit import limiter
from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"


@pytest.fixture(autouse=True)
def limites_limpios():
    limiter.reset()
    yield
    limiter.reset()


async def _usuario(client: AsyncClient) -> dict:
    email = f"limite-{uuid.uuid4().hex[:8]}@example.com"
    return (await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez"))["cookies"]


async def _cambia(client: AsyncClient, cookies: dict, **cuerpo) -> Response:
    client.cookies.clear()
    set_auth_cookies(client, cookies)
    # Contraseña mal: no cambia nada ni manda correos, pero cuenta igual
    datos = {"current_password": "Equivocada123!", **cuerpo}
    r = await client.patch(
        "/api/v1/users/security",
        json=datos,
        headers={"X-CSRF-Token": cookies.get("csrf_token", "")},
    )
    client.cookies.clear()
    return r


def _contrasena() -> dict:
    return {"new_password": "OtraValida123!", "confirm_password": "OtraValida123!"}


async def test_l1_the_eleventh_change_in_an_hour_is_refused(client: AsyncClient):
    """
    Given: Un usuario que ya hizo 10 peticiones de seguridad esta hora
    When: Hace la 11.ª
    Then: 429 TOO_MANY_SECURITY_CHANGES; las 10 primeras pasaron
    """
    cookies = await _usuario(client)
    for i in range(10):
        r = await _cambia(client, cookies, **_contrasena())
        assert r.status_code == 401, f"{i + 1}: {r.status_code} {r.text}"

    r = await _cambia(client, cookies, **_contrasena())

    assert r.status_code == 429
    assert r.json()["error_code"] == "TOO_MANY_SECURITY_CHANGES"


async def test_l2_the_fourth_new_email_in_an_hour_is_refused(client: AsyncClient):
    """
    Given: Un usuario que ya pidió 3 correos nuevos esta hora
    When: Pide el 4.º
    Then: 429 TOO_MANY_EMAIL_CHANGE_REQUESTS
    """
    cookies = await _usuario(client)
    for i in range(3):
        r = await _cambia(client, cookies, new_email=f"nuevo{i}@example.com")
        assert r.status_code == 401, f"{i + 1}: {r.status_code} {r.text}"

    r = await _cambia(client, cookies, new_email="nuevo9@example.com")

    assert r.status_code == 429
    assert r.json()["error_code"] == "TOO_MANY_EMAIL_CHANGE_REQUESTS"


async def test_l3_password_changes_do_not_spend_the_email_allowance(client: AsyncClient):
    """
    Given: Un usuario que cambió la contraseña 5 veces esta hora
    When: Pide un correo nuevo
    Then: No es un 429
    """
    cookies = await _usuario(client)
    for _ in range(5):
        await _cambia(client, cookies, **_contrasena())

    r = await _cambia(client, cookies, new_email="nuevo@example.com")

    assert r.status_code == 401, r.text


async def test_l4_each_user_has_their_own_counter(client: AsyncClient):
    """
    Given: Un usuario que agotó sus 10 peticiones
    When: Otro usuario hace la suya
    Then: No es un 429
    """
    agotado = await _usuario(client)
    for _ in range(11):
        await _cambia(client, agotado, **_contrasena())
    otro = await _usuario(client)

    r = await _cambia(client, otro, **_contrasena())

    assert r.status_code == 401, r.text


async def test_l5_the_429_has_a_fixed_text_without_the_limit(client: AsyncClient):
    """
    Given: Un usuario por encima del límite
    When: Lo rechaza
    Then: Un texto fijo, sin el límite, la ventana ni la clave
    """
    cookies = await _usuario(client)
    for _ in range(10):
        await _cambia(client, cookies, **_contrasena())

    cuerpo = (await _cambia(client, cookies, **_contrasena())).json()

    assert set(cuerpo) == {"detail", "error_code"}
    assert not any(t in cuerpo["detail"] for t in ("10", "hour", "user:"))
