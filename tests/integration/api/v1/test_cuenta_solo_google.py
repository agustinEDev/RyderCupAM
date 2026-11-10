"""
Una cuenta solo-Google, por la API (probador de la release, 8 nov 2026).

  G1 desvincular su único Google: 400, sigue vinculado
  G2 reautenticarse: 409 ACCOUNT_WITHOUT_PASSWORD, no «contraseña incorrecta»
  G3 current-user dice has_password false
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_authenticated_user,
    set_auth_cookies,
    sql_en_la_bd_de_test as _sql,
)

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"


async def _solo_google(client: AsyncClient, email: str) -> dict:
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await _sql("update users set password = null, email_verified = true where email = :e", e=email)
    await _sql(
        "insert into user_oauth_accounts (id, user_id, provider, provider_user_id, provider_email, created_at) "
        "select gen_random_uuid()::text, id, 'google', 'g-' || id, email, now() from users where email = :e",
        e=email,
    )
    set_auth_cookies(client, datos["cookies"])
    return datos


def _csrf(client: AsyncClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token", "")}


async def test_g1_unlinking_the_only_google_is_refused(client: AsyncClient):
    """
    Given: Una cuenta solo con Google (sin contraseña, sin forma de confirmarla)
    When: Intenta desvincular Google
    Then: 403 REAUTHENTICATION_REQUIRED: desvincular pide la marca antes que nada (D4, 8
          nov 2026) y sin contraseña no hay marca; el Google sigue. La app ya no ofrece
          el botón a estas cuentas
    """
    await _solo_google(client, "g1_solo@example.com")

    r = await client.delete("/api/v1/auth/google/unlink", headers=_csrf(client))

    assert r.status_code == 403, r.text
    assert r.json()["error_code"] == "REAUTHENTICATION_REQUIRED"


async def test_g2_reauthenticating_says_there_is_no_password(client: AsyncClient):
    await _solo_google(client, "g2_solo@example.com")

    r = await client.post(
        "/api/v1/auth/reauthenticate", json={"password": CLAVE}, headers=_csrf(client)
    )

    assert r.status_code == 409, r.text
    assert r.json()["error_code"] == "ACCOUNT_WITHOUT_PASSWORD"


async def test_g3_current_user_says_it_has_no_password(client: AsyncClient):
    await _solo_google(client, "g3_solo@example.com")

    r = await client.get("/api/v1/auth/current-user")

    assert r.status_code == 200, r.text
    assert r.json()["has_password"] is False
