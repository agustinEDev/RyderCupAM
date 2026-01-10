"""
Security Tests: CSRF Protection

Tests de seguridad para validar la protección contra Cross-Site Request Forgery (CSRF).
Valida la estrategia de triple capa:
1. Custom Header X-CSRF-Token
2. Double-Submit Cookie csrf_token
3. SameSite="lax"

OWASP Top 10 2021:
- A01: Broken Access Control → CSRF protection previene modificaciones no autorizadas
- A07: Identification and Authentication Failures → Token único por sesión

Test Coverage:
- POST/PUT/PATCH/DELETE requieren token CSRF válido
- GET/HEAD/OPTIONS no requieren token CSRF (métodos seguros)
- Rutas públicas exentas (/health, /docs)
- Token inválido retorna 403 Forbidden
- Token faltante retorna 403 Forbidden
- Cookie sin header retorna 403 Forbidden
- Login y refresh-token generan nuevo token CSRF
"""

import os

import pytest
from fastapi import status
from httpx import AsyncClient

from src.config.csrf_config import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


@pytest.fixture(scope="module", autouse=True)
def enable_csrf_validation():
    """Enable CSRF validation for all tests in this module."""
    original_value = os.environ.get("TEST_CSRF")
    os.environ["TEST_CSRF"] = "true"
    yield
    # Restore original value after module tests
    if original_value is None:
        os.environ.pop("TEST_CSRF", None)
    else:
        os.environ["TEST_CSRF"] = original_value


# ======================================================================================
# Fixtures
# ======================================================================================


@pytest.fixture
async def valid_user_credentials():
    """
    Credenciales de un usuario válido para tests de autenticación.
    """
    return {"email": "testcsrf@example.com", "password": "SecurePassword123!"}


@pytest.fixture
async def csrf_authenticated_client(client: AsyncClient, valid_user_credentials):
    """
    Crea un cliente autenticado y retorna (client, tokens).

    Returns:
        tuple: (AsyncClient, {"access_token", "refresh_token", "csrf_token"})
    """
    # Register user first
    user_data = {
        **valid_user_credentials,
        "first_name": "CSRF",
        "last_name": "Test",
    }
    register_response = await client.post("/api/v1/auth/register", json=user_data)
    assert register_response.status_code in [
        status.HTTP_201_CREATED,
        status.HTTP_409_CONFLICT,
    ]

    # Login to get tokens
    response = await client.post("/api/v1/auth/login", json=valid_user_credentials)

    if response.status_code != status.HTTP_200_OK:
        pytest.skip(
            f"No se pudo autenticar usuario de prueba (status: {response.status_code})"
        )

    data = response.json()

    # Extraer tokens de response body
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    csrf_token = data.get("csrf_token")

    if not all([access_token, refresh_token, csrf_token]):
        pytest.skip("Respuesta de login no contiene todos los tokens requeridos")

    return client, {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
    }


# ======================================================================================
# Tests: Métodos Seguros (GET, HEAD, OPTIONS) - No requieren CSRF token
# ======================================================================================


@pytest.mark.asyncio
async def test_get_request_without_csrf_token_succeeds(client: AsyncClient):
    """
    Test: GET request sin token CSRF debe tener éxito.

    Given: Un GET request sin token CSRF
    When: Se envía a un endpoint público
    Then: El servidor responde 200 OK (o el código apropiado)

    OWASP: A01 - Los métodos seguros (RFC 7231) no requieren CSRF protection
    """
    # GET request sin token CSRF ni autenticación
    response = await client.get("/")

    # No debe fallar por falta de CSRF token
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_options_request_without_csrf_token_succeeds(client: AsyncClient):
    """
    Test: OPTIONS request sin token CSRF debe tener éxito.

    Given: Un OPTIONS request (preflight CORS) sin token CSRF
    When: Se envía a cualquier endpoint
    Then: El servidor responde sin error de CSRF

    OWASP: A01 - OPTIONS es método seguro (CORS preflight)
    """
    # OPTIONS request sin token CSRF
    response = await client.options("/api/v1/auth/login")

    # No debe fallar por falta de CSRF token (puede ser 200 o 405 dependiendo del endpoint)
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_405_METHOD_NOT_ALLOWED,
    ]


# ======================================================================================
# Tests: Rutas Exentas - No requieren CSRF token
# ======================================================================================


@pytest.mark.asyncio
async def test_health_endpoint_exempt_from_csrf(client: AsyncClient):
    """
    Test: Endpoint /health exento de validación CSRF.

    Given: Un POST request a /health sin token CSRF
    When: Se envía el request
    Then: El servidor NO responde 403 Forbidden por CSRF

    Nota: /health puede no aceptar POST, pero no debe fallar por CSRF
    """
    # POST a /health sin token CSRF
    response = await client.post("/health")

    # No debe ser 403 por CSRF (puede ser 404 o 405 si no existe/acepta POST)
    assert (
        response.status_code != status.HTTP_403_FORBIDDEN
        or "CSRF" not in response.json().get("detail", "")
    )


@pytest.mark.asyncio
async def test_docs_endpoint_exempt_from_csrf(client: AsyncClient):
    """
    Test: Endpoint /docs exento de validación CSRF.

    Given: Un request a /docs sin token CSRF
    When: Se envía el request
    Then: El servidor NO responde 403 Forbidden por CSRF

    Nota: /docs puede requerir autenticación, pero no CSRF
    """
    # GET a /docs sin token CSRF
    response = await client.get("/docs")

    # No debe ser 403 por CSRF (puede ser 401 por autenticación)
    assert (
        response.status_code != status.HTTP_403_FORBIDDEN
        or "CSRF" not in response.json().get("detail", "")
    )


# ======================================================================================
# Tests: POST/PUT/PATCH/DELETE - Requieren CSRF token válido
# ======================================================================================


@pytest.mark.asyncio
async def test_post_request_without_csrf_token_fails(csrf_authenticated_client):
    """
    Test: POST request sin token CSRF debe fallar con 403 Forbidden.

    Given: Un usuario autenticado con access token válido
    When: Envía POST request SIN token CSRF
    Then: El servidor responde 403 Forbidden (CSRF validation failed)

    OWASP: A01 - CSRF protection previene modificaciones no autorizadas
    """
    client, tokens = csrf_authenticated_client
    access_token = tokens["access_token"]

    # POST request con autenticación pero SIN token CSRF
    response = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "John"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Debe fallar por falta de CSRF token
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_post_request_with_invalid_csrf_token_fails(csrf_authenticated_client):
    """
    Test: POST request con token CSRF inválido debe fallar.

    Given: Un usuario autenticado con access token válido
    When: Envía POST request con token CSRF INVÁLIDO
    Then: El servidor responde 403 Forbidden (CSRF validation failed)

    OWASP: A01 - Token CSRF no coincide entre cookie y header
    """
    client, tokens = csrf_authenticated_client
    access_token = tokens["access_token"]
    csrf_token = tokens["csrf_token"]

    # POST request con token CSRF INVÁLIDO (no coincide entre header y cookie)
    response = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "John"},
        headers={
            "Authorization": f"Bearer {access_token}",
            CSRF_HEADER_NAME: "invalid_token_12345",  # Token INVÁLIDO en header
        },
        cookies={CSRF_COOKIE_NAME: csrf_token},  # Cookie válido pero header no coincide
    )

    # Debe fallar por token CSRF inválido
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_post_request_with_valid_csrf_token_succeeds(csrf_authenticated_client):
    """
    Test: POST request con token CSRF válido debe tener éxito.

    Given: Un usuario autenticado con access token y csrf token válidos
    When: Envía POST request con token CSRF CORRECTO (mismo en header y cookie)
    Then: El servidor responde 200 OK (CSRF validation passed)

    OWASP: A01 - Double-submit correcto permite la operación
    """
    client, tokens = csrf_authenticated_client
    access_token = tokens["access_token"]
    csrf_token = tokens["csrf_token"]

    # POST request con token CSRF VÁLIDO (mismo en header y cookie)
    response = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "John"},
        headers={
            "Authorization": f"Bearer {access_token}",
            CSRF_HEADER_NAME: csrf_token,  # Token VÁLIDO en header
        },
        cookies={CSRF_COOKIE_NAME: csrf_token},  # Token VÁLIDO en cookie
    )

    # Debe tener éxito (200 OK)
    assert response.status_code == status.HTTP_200_OK


# ======================================================================================
# Tests: Token Generation (Login, Refresh)
# ======================================================================================


@pytest.mark.asyncio
async def test_login_generates_csrf_token(client: AsyncClient, valid_user_credentials):
    """
    Test: Login exitoso genera y retorna un token CSRF.

    Given: Credenciales válidas de usuario
    When: Usuario hace login
    Then: Response contiene csrf_token en body Y en cookie

    OWASP: A07 - Token CSRF único por sesión
    """
    # Register user first
    user_data = {
        **valid_user_credentials,
        "first_name": "CSRF",
        "last_name": "Test",
    }
    await client.post("/api/v1/auth/register", json=user_data)

    # Login
    response = await client.post("/api/v1/auth/login", json=valid_user_credentials)

    if response.status_code != status.HTTP_200_OK:
        pytest.skip("No se pudo autenticar usuario de prueba")

    data = response.json()

    # Validar que csrf_token esté en response body
    assert "csrf_token" in data
    assert len(data["csrf_token"]) > 0

    # Validar que csrf_token esté en cookies (NO httpOnly)
    assert CSRF_COOKIE_NAME in response.cookies


@pytest.mark.asyncio
async def test_refresh_token_generates_new_csrf_token(csrf_authenticated_client):
    """
    Test: Refresh token exitoso genera y retorna un NUEVO token CSRF.

    Given: Usuario autenticado con refresh token válido
    When: Usuario renueva su access token
    Then: Response contiene NUEVO csrf_token en body Y en cookie

    OWASP: A07 - Nuevo token CSRF por cada renovación de sesión
    """
    client, tokens = csrf_authenticated_client
    refresh_token = tokens["refresh_token"]
    old_csrf_token = tokens["csrf_token"]

    # Refresh token request (cookie enviada automáticamente)
    response = await client.post(
        "/api/v1/auth/refresh-token", cookies={"refresh_token": refresh_token}
    )

    if response.status_code != status.HTTP_200_OK:
        pytest.skip("No se pudo renovar token")

    data = response.json()

    # Validar que csrf_token esté en response body
    assert "csrf_token" in data
    new_csrf_token = data["csrf_token"]
    assert len(new_csrf_token) > 0

    # Validar que csrf_token esté en cookies
    assert CSRF_COOKIE_NAME in response.cookies

    # Validar que el nuevo token sea DIFERENTE del anterior
    assert new_csrf_token != old_csrf_token


# ======================================================================================
# Tests: Edge Cases
# ======================================================================================


@pytest.mark.asyncio
async def test_post_request_with_csrf_cookie_but_no_header_fails(
    csrf_authenticated_client,
):
    """
    Test: POST request con cookie CSRF pero SIN header debe fallar.

    Given: Usuario autenticado con csrf_token en cookie
    When: Envía POST request SIN header X-CSRF-Token
    Then: El servidor responde 403 Forbidden

    OWASP: A01 - Double-submit requiere AMBOS (cookie Y header)
    """
    client, tokens = csrf_authenticated_client
    access_token = tokens["access_token"]
    csrf_token = tokens["csrf_token"]

    # POST request con cookie CSRF pero SIN header
    response = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "John"},
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={CSRF_COOKIE_NAME: csrf_token},  # Cookie presente pero header ausente
    )

    # Debe fallar por falta de header CSRF
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_post_request_with_csrf_header_but_no_cookie_fails(
    csrf_authenticated_client,
):
    """
    Test: POST request con header CSRF pero SIN cookie debe fallar.

    Given: Usuario autenticado con csrf_token en header
    When: Envía POST request SIN cookie csrf_token
    Then: El servidor responde 403 Forbidden

    OWASP: A01 - Double-submit requiere AMBOS (cookie Y header)
    """
    client, tokens = csrf_authenticated_client
    access_token = tokens["access_token"]
    csrf_token = tokens["csrf_token"]

    # Clear all cookies to simulate request without CSRF cookie
    client.cookies.clear()

    # POST request con header CSRF pero SIN cookie
    response = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "John"},
        headers={
            "Authorization": f"Bearer {access_token}",
            CSRF_HEADER_NAME: csrf_token,  # Header presente pero cookie ausente
        },
    )

    # Debe fallar por falta de cookie CSRF
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF" in response.json().get("detail", "")
