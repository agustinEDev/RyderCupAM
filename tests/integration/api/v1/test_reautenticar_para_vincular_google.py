"""
Vincular Google pide la contraseña actual (BE #753, punto 2, decidido el 7 nov).

Con solo la sesión, una robada podía añadir un Google que sobrevive a restablecer la
contraseña. Ahora: POST /auth/reauthenticate con la contraseña deja una marca de 5
minutos (cookie firmada, httpOnly), y /auth/google/link la exige y la gasta.

  P1 contraseña correcta: 200 y la marca, httpOnly, de 5 minutos, solo para /auth/google
  P2 contraseña incorrecta: 401 CURRENT_PASSWORD_INCORRECT, sin marca
  P3 los intentos cuentan en el límite de seguridad: el 11.º en la hora, 429
  P4 vincular sin marca: 403 REAUTHENTICATION_REQUIRED, sin gastar el código de Google
  P5 con marca: vincula y la marca se borra; otra vez con la misma, 403
  P6 la marca de otro usuario no sirve
  P7 la marca caducada no sirve
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


async def _usuario(client: AsyncClient, email: str) -> dict:
    from tests.integration.api.v1.test_sesion_desactivada_y_codigos import _sql

    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await _sql("update users set email_verified = true where email = :e", e=email)
    return datos


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


def _csrf(client: AsyncClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token", "")}


async def _reautentica(client: AsyncClient, clave: str = CLAVE) -> Response:
    return await client.post(
        "/api/v1/auth/reauthenticate", json={"password": clave}, headers=_csrf(client)
    )


async def _vincula(client: AsyncClient) -> Response:
    return await client.post(
        "/api/v1/auth/google/link", json={"authorization_code": "code"}, headers=_csrf(client)
    )


def _cookie_de_la_marca(r: Response) -> str | None:
    for k, v in r.headers.multi_items():
        if k == "set-cookie" and v.startswith(f"{reautenticacion.COOKIE}="):
            return v
    return None


async def test_p1_the_right_password_leaves_a_five_minute_mark(client: AsyncClient):
    datos = await _usuario(client, "p1@example.com")
    set_auth_cookies(client, datos["cookies"])

    r = await _reautentica(client)

    assert r.status_code == 200, r.text
    cookie = _cookie_de_la_marca(r)
    assert cookie is not None
    assert "HttpOnly" in cookie and "Max-Age=300" in cookie
    assert "Path=/api/v1/auth/google" in cookie


async def test_p2_a_wrong_password_leaves_no_mark(client: AsyncClient):
    datos = await _usuario(client, "p2@example.com")
    set_auth_cookies(client, datos["cookies"])

    r = await _reautentica(client, "Equivocada123!")

    assert r.status_code == 401
    assert r.json()["error_code"] == "CURRENT_PASSWORD_INCORRECT"
    assert _cookie_de_la_marca(r) is None


async def test_p3_attempts_count_in_the_security_limit(client: AsyncClient):
    datos = await _usuario(client, "p3@example.com")
    set_auth_cookies(client, datos["cookies"])
    for _ in range(10):
        await _reautentica(client, "Equivocada123!")

    r = await _reautentica(client)

    assert r.status_code == 429
    assert r.json()["error_code"] == "TOO_MANY_SECURITY_CHANGES"


async def test_p4_linking_without_the_mark_is_refused_before_using_the_code(
    client: AsyncClient,
):
    datos = await _usuario(client, "p4@example.com")
    set_auth_cookies(client, datos["cookies"])
    google = _google("p4@example.com")

    r = await _vincula(client)

    assert r.status_code == 403
    assert r.json()["error_code"] == "REAUTHENTICATION_REQUIRED"
    google.exchange_code_for_user_info.assert_not_awaited()


async def test_p5_the_mark_links_once(client: AsyncClient):
    datos = await _usuario(client, "p5@example.com")
    set_auth_cookies(client, datos["cookies"])
    marca = _cookie_de_la_marca(await _reautentica(client)).split(";")[0].split("=", 1)[1]
    _google("p5@example.com")

    r = await _vincula(client)

    assert r.status_code == 200, r.text
    assert "Max-Age=0" in (_cookie_de_la_marca(r) or "")
    # La misma marca, otra vez (aunque el navegador no la hubiera borrado)
    client.cookies.set(reautenticacion.COOKIE, marca)
    await client.delete("/api/v1/auth/google/unlink", headers=_csrf(client))
    otra = await _vincula(client)
    assert otra.status_code == 403
    assert otra.json()["error_code"] == "REAUTHENTICATION_REQUIRED"


async def test_p6_another_users_mark_does_not_count(client: AsyncClient):
    ajena = reautenticacion.emite("00000000-0000-0000-0000-000000000001")
    datos = await _usuario(client, "p6@example.com")
    set_auth_cookies(client, datos["cookies"])
    client.cookies.set(reautenticacion.COOKIE, ajena)
    _google("p6@example.com")

    r = await _vincula(client)

    assert r.status_code == 403


async def test_p7_an_expired_mark_does_not_count(client: AsyncClient):
    datos = await _usuario(client, "p7@example.com")
    caducada = reautenticacion.emite(datos["user"]["id"], dura=timedelta(seconds=-1))
    set_auth_cookies(client, datos["cookies"])
    client.cookies.set(reautenticacion.COOKIE, caducada)
    _google("p7@example.com")

    r = await _vincula(client)

    assert r.status_code == 403
