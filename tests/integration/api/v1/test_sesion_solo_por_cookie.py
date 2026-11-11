"""
La sesión viaja solo en cookies httpOnly (F-03, fase 3 del plan a 9, release 2.58.0).

Hasta la 2.57.0 el login, Google y la renovación devolvían también los tokens en el
cuerpo, y la API aceptaba `Authorization: Bearer`. El front 2.73.0 ya no los lee ni
los manda: un script inyectado no tiene ya credenciales que leer.

  B1 login: el cuerpo sin access_token, refresh_token ni token_type; cookies como hoy
  B2 Google: lo mismo
  B3 renovar: el cuerpo sin access_token ni token_type; cookie de acceso nueva
  B4 el esquema de las tres respuestas, sin esos campos
  C1 solo Bearer, sin cookie: 401
  C2 cookie de A y Bearer de B: responde A
  C6 solo la cookie: funciona
  C7 el esquema declara la cookie, no Bearer
  C8 el 401 sigue diciendo WWW-Authenticate: Bearer (la cabecera estándar)
  A1 el GET viejo de validar el enlace de restablecer: 404
  A5 y ya no está en el esquema
  D1/D2 Google (login y vincular) sin code_verifier: 422 sin llamar a Google
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_google_oauth_service
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
FUERA_DEL_CUERPO = {"access_token", "refresh_token", "token_type"}


@pytest.fixture(autouse=True)
def sin_google_de_verdad():
    """Quita el doble de Google al acabar cada test."""
    yield
    app.dependency_overrides.pop(get_google_oauth_service, None)


def _google(email: str) -> AsyncMock:
    """Un Google falso que responde con ese correo verificado."""
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


async def _alta(client: AsyncClient, email: str) -> None:
    """Da de alta una cuenta (sin entrar)."""
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Lopez",
            "accept_terms": True,
        },
        headers={"X-Test-Client-ID": f"alta-{uuid.uuid4()}"},
    )
    assert r.status_code == 201, r.text


async def _login(client: AsyncClient, email: str):
    """Entra con correo y contraseña."""
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"X-Test-Client-ID": f"login-{uuid.uuid4()}"},
    )


# --- B: los tokens, fuera del cuerpo -------------------------------------------------


async def test_b1_login_body_has_no_tokens_and_the_cookies_are_set(client: AsyncClient):
    """
    Given: Una cuenta
    When: Entra con correo y contraseña
    Then: El cuerpo no trae ni access_token ni refresh_token ni token_type; sí csrf_token,
          user, device_id y email_verification_required; y las tres cookies llegan
    """
    email = "b1-sin-tokens@example.com"
    await _alta(client, email)

    r = await _login(client, email)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert FUERA_DEL_CUERPO.isdisjoint(cuerpo), sorted(cuerpo)
    assert {"csrf_token", "user", "device_id", "email_verification_required"} <= set(cuerpo)
    assert {"access_token", "refresh_token", "csrf_token"} <= set(r.cookies)


async def test_b2_google_login_body_has_no_tokens(client: AsyncClient):
    """
    Given: Un login con Google (con su code_verifier)
    When: Entra
    Then: El cuerpo no trae tokens; las cookies, sí
    """
    _google("b2-google@gmail.com")

    r = await client.post(
        "/api/v1/auth/google",
        json={"authorization_code": "code", "code_verifier": VERIFIER},
        headers={"X-Test-Client-ID": "b2"},
    )

    assert r.status_code == 200, r.text
    assert FUERA_DEL_CUERPO.isdisjoint(r.json()), sorted(r.json())
    assert {"csrf_token", "user", "device_id"} <= set(r.json())
    assert {"access_token", "refresh_token", "csrf_token"} <= set(r.cookies)


async def test_b3_refresh_body_has_no_access_token(client: AsyncClient):
    """
    Given: Una sesión con sus cookies
    When: Renueva la sesión
    Then: El cuerpo no trae access_token ni token_type; la cookie de acceso se pone
    """
    email = "b3-renovar@example.com"
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    set_auth_cookies(client, datos["cookies"])

    r = await client.post("/api/v1/auth/refresh-token")

    assert r.status_code == 200, r.text
    assert FUERA_DEL_CUERPO.isdisjoint(r.json()), sorted(r.json())
    assert {"csrf_token", "user", "device_id", "message"} <= set(r.json())
    # La cookie de acceso se vuelve a poner (en el mismo segundo el JWT puede ser igual)
    assert r.cookies.get("access_token")


@pytest.mark.parametrize(
    ("ruta", "metodo"),
    [
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/google", "post"),
        ("/api/v1/auth/refresh-token", "post"),
    ],
)
async def test_b4_the_schema_of_the_three_answers_has_no_tokens(ruta: str, metodo: str):
    """
    Given: El esquema OpenAPI
    When: Se mira la respuesta 200 de login, Google y renovar
    Then: Ninguna declara access_token, refresh_token ni token_type
    """
    esquema = app.openapi()
    ref = esquema["paths"][ruta][metodo]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    propiedades = esquema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]

    assert FUERA_DEL_CUERPO.isdisjoint(propiedades), sorted(propiedades)


# --- C: sin Authorization: Bearer ------------------------------------------------------


async def test_c1_only_a_bearer_header_is_401(client: AsyncClient):
    """
    Given: El access token válido de una cuenta, pero sin cookies
    When: Pide su perfil con Authorization: Bearer
    Then: 401, con la cabecera estándar WWW-Authenticate (C8)
    """
    datos = await create_authenticated_user(client, "c1-bearer@example.com", CLAVE, "Ana", "Lopez")
    client.cookies.clear()

    r = await client.get(
        "/api/v1/auth/current-user",
        headers={"Authorization": f"Bearer {datos['cookies']['access_token']}"},
    )

    assert r.status_code == 401, r.text
    assert r.headers.get("www-authenticate") == "Bearer"


async def test_c2_cookie_of_a_and_bearer_of_b_answers_a(client: AsyncClient):
    """
    Given: La cookie de A y la cabecera Bearer de B
    When: Pide el usuario actual
    Then: Responde A
    """
    a = await create_authenticated_user(client, "c2-a@example.com", CLAVE, "Ana", "Lopez")
    b = await create_authenticated_user(client, "c2-b@example.com", CLAVE, "Bea", "Lopez")
    set_auth_cookies(client, a["cookies"])

    r = await client.get(
        "/api/v1/auth/current-user",
        headers={"Authorization": f"Bearer {b['cookies']['access_token']}"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["email"] == "c2-a@example.com"


async def test_c6_only_the_cookie_works(client: AsyncClient):
    """
    Given: Solo la cookie de sesión
    When: Pide el usuario actual
    Then: 200
    """
    datos = await create_authenticated_user(client, "c6-cookie@example.com", CLAVE, "Ana", "Lopez")
    set_auth_cookies(client, datos["cookies"])

    r = await client.get("/api/v1/auth/current-user")

    assert r.status_code == 200, r.text


def test_c7_the_schema_declares_the_cookie_not_bearer():
    """
    Given: El esquema OpenAPI
    When: Se miran sus esquemas de seguridad
    Then: Hay uno de cookie `access_token` y ninguno http bearer
    """
    esquemas = app.openapi()["components"].get("securitySchemes", {}).values()

    assert not [e for e in esquemas if e.get("type") == "http"], list(esquemas)
    assert [e for e in esquemas if e.get("in") == "cookie" and e.get("name") == "access_token"]


# --- A: el GET viejo del enlace de restablecer -----------------------------------------


async def test_a1_the_old_get_to_validate_a_reset_link_is_gone(client: AsyncClient):
    """
    Given: Un token de restablecer con la forma de uno de verdad
    When: Se valida por el GET viejo, con el token en la ruta
    Then: 404: la ruta ya no existe
    """
    r = await client.get(f"/api/v1/auth/validate-reset-token/{'a' * 43}")

    assert r.status_code == 404


def test_a5_the_old_get_is_not_in_the_schema():
    """
    Given: El esquema OpenAPI
    When: Se buscan las rutas de validar el enlace
    Then: Solo queda la del POST
    """
    rutas = [r for r in app.openapi()["paths"] if r.startswith("/api/v1/auth/validate-reset-token")]

    assert rutas == ["/api/v1/auth/validate-reset-token"]
    assert set(app.openapi()["paths"][rutas[0]]) == {"post"}


# --- D: PKCE obligatorio -----------------------------------------------------------------


async def test_d1_google_login_without_verifier_is_422_without_calling_google(
    client: AsyncClient,
):
    """
    Given: Un login con Google sin code_verifier (un front anterior a la 2.73.0)
    When: Llega a la API
    Then: 422, y el código no se canjea
    """
    google = _google("d1-sin-verifier@gmail.com")

    r = await client.post(
        "/api/v1/auth/google",
        json={"authorization_code": "code"},
        headers={"X-Test-Client-ID": "d1"},
    )

    assert r.status_code == 422, r.text
    google.exchange_code_for_user_info.assert_not_awaited()


async def test_d2_linking_google_without_verifier_is_422_without_calling_google(
    client: AsyncClient,
):
    """
    Given: Una cuenta verificada que acaba de escribir su contraseña
    When: Vincula Google sin code_verifier
    Then: 422, y el código no se canjea
    """
    email = "d2-vincula@example.com"
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await sql_en_la_bd_de_test("update users set email_verified = true where email = :e", e=email)
    google = _google(email)
    set_auth_cookies(client, datos["cookies"])
    csrf = {"X-CSRF-Token": client.cookies.get("csrf_token", "")}
    r = await client.post("/api/v1/auth/reauthenticate", json={"password": CLAVE}, headers=csrf)
    assert r.status_code == 200, r.text

    r = await client.post(
        "/api/v1/auth/google/link", json={"authorization_code": "code"}, headers=csrf
    )

    assert r.status_code == 422, r.text
    google.exchange_code_for_user_info.assert_not_awaited()
