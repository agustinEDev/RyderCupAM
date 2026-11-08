"""
Desvincular Google pide la contraseña actual, como vincularlo (tabla D aprobada por
Agustín el 8 nov 2026). Con solo una sesión robada se podía quitar el Google del dueño.

  D1 con la marca de /auth/reauthenticate: desvincula y la marca se gasta (se borra)
  D2 sin marca, ya usada, de otro usuario o caducada: 403 REAUTHENTICATION_REQUIRED y el
     Google sigue
  D3 la marca se gasta al empezar, aunque luego falle (sin Google: 400)
  D4 la marca se mira antes que nada: sin ella, 403 tenga o no Google
  D5 una marca, una acción: la gastada al vincular no sirve para desvincular
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, Response

from main import app
from src.config.dependencies import get_google_oauth_service
from src.config.rate_limit import limiter
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.infrastructure.security import reautenticacion
from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"


@pytest.fixture(autouse=True)
def limpio():
    limiter.reset()
    yield
    limiter.reset()
    app.dependency_overrides.pop(get_google_oauth_service, None)


def _csrf(client: AsyncClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token", "")}


async def _usuario(client: AsyncClient, email: str) -> dict:
    from tests.integration.api.v1.test_sesion_desactivada_y_codigos import _sql

    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await _sql("update users set email_verified = true where email = :e", e=email)
    set_auth_cookies(client, datos["cookies"])
    return datos


async def _con_google(client: AsyncClient, email: str) -> dict:
    """Un usuario con contraseña y su Google vinculado (con su marca, ya gastada)."""
    datos = await _usuario(client, email)
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
    await _reautentica(client)
    vinculo = await client.post(
        "/api/v1/auth/google/link", json={"authorization_code": "code"}, headers=_csrf(client)
    )
    assert vinculo.status_code == 200, vinculo.text
    return datos


async def _reautentica(client: AsyncClient) -> Response:
    r = await client.post(
        "/api/v1/auth/reauthenticate", json={"password": CLAVE}, headers=_csrf(client)
    )
    assert r.status_code == 200, r.text
    return r


async def _desvincula(client: AsyncClient) -> Response:
    return await client.delete("/api/v1/auth/google/unlink", headers=_csrf(client))


async def _sigue_vinculado(email: str) -> bool:
    from tests.integration.api.v1.test_terms_acceptance_endpoints import _sql

    filas = await _sql(
        "select count(*) from user_oauth_accounts o join users u on u.id = o.user_id "
        "where u.email = :e",
        {"e": email},
    )
    return filas[0][0] == 1


def _cookie_de_la_marca(r: Response) -> str | None:
    for k, v in r.headers.multi_items():
        if k == "set-cookie" and v.startswith(f"{reautenticacion.COOKIE}="):
            return v
    return None


def _ponle_la_marca(client: AsyncClient, marca: str) -> None:
    client.cookies.set(reautenticacion.COOKIE, marca, path=reautenticacion.RUTA)


async def test_unlink_with_the_mark_unlinks_and_spends_it(client: AsyncClient):
    """
    Given: Un usuario con Google y la contraseña recién confirmada
    When: Desvincula Google
    Then: 200, la marca se borra y el Google ya no está (D1)
    """
    email = "d1@example.com"
    await _con_google(client, email)
    await _reautentica(client)

    r = await _desvincula(client)

    assert r.status_code == 200, r.text
    assert "Max-Age=0" in (_cookie_de_la_marca(r) or "")
    assert not await _sigue_vinculado(email)


async def test_unlink_without_the_mark_answers_403_and_keeps_google(client: AsyncClient):
    """
    Given: Un usuario con Google, sin la marca
    When: Desvincula Google
    Then: 403 REAUTHENTICATION_REQUIRED y el Google sigue (D2)
    """
    email = "d2a@example.com"
    await _con_google(client, email)
    client.cookies.delete(reautenticacion.COOKIE)

    r = await _desvincula(client)

    assert r.status_code == 403
    assert r.json()["error_code"] == "REAUTHENTICATION_REQUIRED"
    assert await _sigue_vinculado(email)


async def test_unlink_with_a_spent_mark_answers_403(client: AsyncClient):
    """
    Given: Un usuario con Google y una marca ya gastada
    When: Desvincula Google
    Then: 403 y el Google sigue (D2)
    """
    email = "d2b@example.com"
    datos = await _con_google(client, email)
    marca = reautenticacion.emite(datos["user"]["id"])
    _ponle_la_marca(client, marca)
    assert reautenticacion.gasta_si_vale(marca, datos["user"]["id"])

    r = await _desvincula(client)

    assert r.status_code == 403
    assert r.json()["error_code"] == "REAUTHENTICATION_REQUIRED"
    assert await _sigue_vinculado(email)


async def test_unlink_with_another_users_mark_answers_403(client: AsyncClient):
    """
    Given: Un usuario con Google y la marca de otro usuario
    When: Desvincula Google
    Then: 403 y el Google sigue (D2)
    """
    email = "d2c@example.com"
    await _con_google(client, email)
    _ponle_la_marca(client, reautenticacion.emite("00000000-0000-0000-0000-000000000001"))

    r = await _desvincula(client)

    assert r.status_code == 403
    assert await _sigue_vinculado(email)


async def test_unlink_with_an_expired_mark_answers_403(client: AsyncClient):
    """
    Given: Un usuario con Google y una marca caducada
    When: Desvincula Google
    Then: 403 y el Google sigue (D2)
    """
    email = "d2d@example.com"
    datos = await _con_google(client, email)
    _ponle_la_marca(client, reautenticacion.emite(datos["user"]["id"], dura=timedelta(seconds=-1)))

    r = await _desvincula(client)

    assert r.status_code == 403
    assert await _sigue_vinculado(email)


async def test_unlink_failing_after_the_mark_still_spends_it(client: AsyncClient):
    """
    Given: Un usuario sin Google con una marca válida
    When: Desvincula dos veces con la misma marca
    Then: 400 la primera (sin Google) y 403 la segunda: se gastó al empezar (D3)
    """
    datos = await _usuario(client, "d3@example.com")
    marca = reautenticacion.emite(datos["user"]["id"])
    _ponle_la_marca(client, marca)

    sin_google = await _desvincula(client)
    _ponle_la_marca(client, marca)
    otra_vez = await _desvincula(client)

    assert sin_google.status_code == 400
    assert otra_vez.status_code == 403
    assert otra_vez.json()["error_code"] == "REAUTHENTICATION_REQUIRED"


async def test_unlink_without_the_mark_answers_403_even_without_google(client: AsyncClient):
    """
    Given: Un usuario sin Google y sin marca
    When: Desvincula Google
    Then: 403, no 400: el 403 no dice si hay Google (D4)
    """
    await _usuario(client, "d4@example.com")

    r = await _desvincula(client)

    assert r.status_code == 403
    assert r.json()["error_code"] == "REAUTHENTICATION_REQUIRED"


async def test_unlink_with_the_mark_spent_on_linking_answers_403(client: AsyncClient):
    """
    Given: Un usuario que confirmó la contraseña y vinculó Google con esa marca
    When: Desvincula con la misma marca
    Then: 403 y el Google sigue: una marca, una acción (D5)
    """
    email = "d5@example.com"
    datos = await _usuario(client, email)
    marca = _cookie_de_la_marca(await _reautentica(client)).split(";")[0].split("=", 1)[1]
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
    vinculo = await client.post(
        "/api/v1/auth/google/link", json={"authorization_code": "code"}, headers=_csrf(client)
    )
    assert vinculo.status_code == 200, vinculo.text
    assert datos["user"]["id"]
    _ponle_la_marca(client, marca)

    r = await _desvincula(client)

    assert r.status_code == 403
    assert await _sigue_vinculado(email)
