"""
Un 401 tardío del refresco no borra la cookie de una sesión más nueva (BE #734).

  S1 cerró sesión y volvió a entrar en el mismo dispositivo; llega tarde un refresco con
     la cookie vieja → 401 SESSION_REJECTED, pero sin borrar la cookie (es la nueva)
  S2 cerró sesión y no volvió a entrar → 401 y se borra la cookie, como hoy
  S4 sin cookie → 401 y no se borra nada, como hoy
"""

import uuid

import pytest
from httpx import AsyncClient, Response

from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"


def _borra_la_cookie_de_refresco(r: Response) -> bool:
    return any(
        k == "set-cookie" and v.startswith("refresh_token=") and "Max-Age=0" in v
        for k, v in r.headers.multi_items()
    )


async def _cierra_sesion(client: AsyncClient, cookies: dict) -> None:
    set_auth_cookies(client, cookies)
    r = await client.post(
        "/api/v1/auth/logout", json={}, headers={"X-CSRF-Token": cookies.get("csrf_token", "")}
    )
    client.cookies.clear()
    assert r.status_code == 200, r.text


async def _refresca_con(client: AsyncClient, cookies: dict) -> Response:
    client.cookies.clear()
    set_auth_cookies(client, cookies)
    r = await client.post("/api/v1/auth/refresh-token")
    client.cookies.clear()
    return r


async def test_s1_a_late_rejection_does_not_delete_the_new_session_cookie(client: AsyncClient):
    """
    Given: Una sesión que cerró y otra nueva en el mismo dispositivo
    When: Llega tarde un refresco con la cookie de la vieja
    Then: 401 SESSION_REJECTED, sin borrar la cookie de refresco
    """
    email = f"s1-{uuid.uuid4().hex[:8]}@example.com"
    vieja = (await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez"))["cookies"]
    await _cierra_sesion(client, vieja)
    client.cookies.set("device_id", vieja["device_id"])
    nuevo = await client.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
    client.cookies.clear()
    assert nuevo.status_code == 200, nuevo.text

    r = await _refresca_con(client, vieja)

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_REJECTED"
    assert not _borra_la_cookie_de_refresco(r)


async def test_s2_without_a_new_session_the_cookie_is_deleted(client: AsyncClient):
    """
    Given: Una sesión que cerró, sin otra después
    When: Refresca con su cookie
    Then: 401 y se borra la cookie de refresco, como hoy
    """
    email = f"s2-{uuid.uuid4().hex[:8]}@example.com"
    vieja = (await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez"))["cookies"]
    await _cierra_sesion(client, vieja)

    r = await _refresca_con(client, vieja)

    assert r.status_code == 401
    assert _borra_la_cookie_de_refresco(r)


async def test_s4_without_a_cookie_nothing_is_deleted(client: AsyncClient):
    """
    Given: Una petición sin cookie de refresco
    When: Refresca
    Then: 401 SESSION_ENDED y no se borra nada
    """
    client.cookies.clear()

    r = await client.post("/api/v1/auth/refresh-token")

    assert r.status_code == 401
    assert r.json()["error_code"] == "SESSION_ENDED"
    assert not _borra_la_cookie_de_refresco(r)


async def test_s2_a_newer_session_that_also_closed_does_not_keep_the_cookie(client: AsyncClient):
    """
    Given: Cerró sesión, volvió a entrar en el mismo dispositivo y también cerró esa
    When: Refresca con la cookie de la primera
    Then: 401 y se borra la cookie: la sesión nueva tampoco está viva (con la BD real)
    """
    email = f"s2b-{uuid.uuid4().hex[:8]}@example.com"
    vieja = (await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez"))["cookies"]
    await _cierra_sesion(client, vieja)
    client.cookies.set("device_id", vieja["device_id"])
    nuevo = await client.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
    nueva = dict(nuevo.cookies)
    client.cookies.clear()
    await _cierra_sesion(client, {**vieja, **nueva})

    r = await _refresca_con(client, vieja)

    assert r.status_code == 401
    assert _borra_la_cookie_de_refresco(r)
