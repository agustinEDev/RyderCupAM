"""
Tests de Integración para httpOnly Cookies (v1.8.0).

Estos tests verifican que la implementación de cookies httpOnly funciona correctamente
para proteger contra ataques XSS (OWASP A01/A02).

Tests incluidos:
1. Login establece cookie httpOnly
2. Autenticación con cookie (sin header Authorization)
3. Logout elimina cookie httpOnly
4. Verify email establece cookie httpOnly
5. Middleware dual (cookie tiene prioridad sobre header)

Arquitectura:
- Capa: Integration Tests
- Módulo: User (Authentication)
- Feature: httpOnly Cookies (v1.8.0)
"""
import pytest
from httpx import AsyncClient

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO


@pytest.mark.asyncio
class TestHttpOnlyCookies:
    """Tests de integración para httpOnly cookies en autenticación."""

    @pytest.fixture
    def test_user_data(self) -> dict:
        """Fixture con datos de usuario para tests de cookies."""
        return {
            "email": "cookie_test@example.com",
            "password": "SecureP@ssw0rd123",
            "first_name": "Cookie",
            "last_name": "Tester",
        }

    async def test_login_sets_httponly_cookie(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /login establece cookie httpOnly con el JWT.

        Given: Un usuario registrado en el sistema
        When: El usuario hace login con credenciales válidas
        Then:
            - HTTP 200 OK
            - Response body contiene access_token (LEGACY)
            - Response headers contienen Set-Cookie con httpOnly flag
            - Cookie tiene nombre "access_token"
            - Cookie tiene flags: HttpOnly, SameSite=lax, Path=/
        """
        # Given: Registrar usuario
        register_payload = RegisterUserRequestDTO(
            email=test_user_data["email"],
            password=test_user_data["password"],
            first_name=test_user_data["first_name"],
            last_name=test_user_data["last_name"],
        )
        await client.post("/api/v1/auth/register", json=register_payload.model_dump())

        # When: Hacer login
        login_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)

        # Then: Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data  # LEGACY: token en body

        # Then: Verificar cookie httpOnly en headers
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None, "Set-Cookie header debe existir"

        # Verificar que la cookie se llama "access_token"
        assert "access_token=" in set_cookie_header

        # Verificar flags de seguridad
        assert "HttpOnly" in set_cookie_header, "Cookie debe tener flag HttpOnly"
        assert "SameSite=lax" in set_cookie_header, "Cookie debe tener SameSite=lax"
        assert "Path=/" in set_cookie_header, "Cookie debe tener Path=/"
        assert "Max-Age=900" in set_cookie_header, "Cookie debe expirar en 15 minutos"

        # En producción (HTTPS), también debería tener Secure
        # En desarrollo (HTTP), Secure no está presente
        # assert "Secure" in set_cookie_header (solo en producción)

    async def test_authentication_with_cookie_without_header(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: GET /current-user funciona con cookie httpOnly (sin header Authorization).

        Este test verifica que el middleware dual (cookies + headers) funciona correctamente.

        Given: Un usuario autenticado con cookie httpOnly
        When: El usuario hace request a endpoint protegido SIN header Authorization
        Then:
            - HTTP 200 OK
            - Response contiene datos del usuario autenticado
            - Autenticación funciona solo con cookie (prioridad 1)
        """
        # Given: Registrar y hacer login (obtener cookie)
        register_payload = RegisterUserRequestDTO(
            email=test_user_data["email"],
            password=test_user_data["password"],
            first_name=test_user_data["first_name"],
            last_name=test_user_data["last_name"],
        )
        await client.post("/api/v1/auth/register", json=register_payload.model_dump())

        login_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200

        # La cookie ya está establecida en el cliente (httpx maneja cookies automáticamente)

        # When: Request a endpoint protegido SIN header Authorization
        # IMPORTANTE: NO pasamos header Authorization, solo confiamos en la cookie
        response = await client.get("/api/v1/auth/current-user")

        # Then: Autenticación funciona solo con cookie
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["first_name"] == test_user_data["first_name"]
        assert data["last_name"] == test_user_data["last_name"]

    async def test_logout_deletes_httponly_cookie(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /logout elimina cookie httpOnly del navegador.

        Given: Un usuario autenticado con cookie httpOnly
        When: El usuario hace logout
        Then:
            - HTTP 200 OK
            - Response body contiene mensaje de confirmación
            - Response headers contienen Set-Cookie con Max-Age=0 (eliminar cookie)
            - Cookie "access_token" invalidada
        """
        # Given: Registrar y hacer login (obtener cookie)
        register_payload = RegisterUserRequestDTO(
            email=test_user_data["email"],
            password=test_user_data["password"],
            first_name=test_user_data["first_name"],
            last_name=test_user_data["last_name"],
        )
        await client.post("/api/v1/auth/register", json=register_payload.model_dump())

        login_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200

        # When: Hacer logout
        logout_payload = {}  # LogoutRequestDTO puede estar vacío
        response = await client.post("/api/v1/auth/logout", json=logout_payload)

        # Then: Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # El mensaje puede ser "Logout exitoso" o similar
        assert "logout" in data["message"].lower() or "exitoso" in data["message"].lower()

        # Then: Verificar que cookie fue eliminada
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None, "Set-Cookie header debe existir para eliminar cookie"

        # Verificar que la cookie se invalida (Max-Age=0)
        assert "access_token=" in set_cookie_header
        assert "Max-Age=0" in set_cookie_header or "Expires=" in set_cookie_header

    async def test_verify_email_sets_httponly_cookie(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /verify-email establece cookie httpOnly (auto-login después de verificación).

        Given: Un usuario registrado con email no verificado
        When: El usuario verifica su email con token válido
        Then:
            - HTTP 200 OK
            - Response body contiene access_token (LEGACY)
            - Response headers contienen Set-Cookie con httpOnly flag
            - Usuario autenticado automáticamente
        """
        # Given: Registrar usuario (genera token de verificación)
        register_payload = RegisterUserRequestDTO(
            email=test_user_data["email"],
            password=test_user_data["password"],
            first_name=test_user_data["first_name"],
            last_name=test_user_data["last_name"],
        )
        register_response = await client.post(
            "/api/v1/auth/register",
            json=register_payload.model_dump()
        )
        assert register_response.status_code == 201

        # Obtener token de verificación desde la base de datos
        # (En tests, podemos acceder directamente a la BD)
        from tests.conftest import get_user_by_email
        user = await get_user_by_email(client, test_user_data["email"])
        verification_token = user.verification_token
        assert verification_token is not None

        # When: Verificar email
        verify_payload = {"token": verification_token}
        response = await client.post("/api/v1/auth/verify-email", json=verify_payload)

        # Then: Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data  # LEGACY: token en body
        assert data["email_verification_required"] is False

        # Then: Verificar cookie httpOnly en headers
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None, "Set-Cookie header debe existir"
        assert "access_token=" in set_cookie_header
        assert "HttpOnly" in set_cookie_header

    async def test_middleware_dual_cookie_has_priority_over_header(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: Middleware dual da prioridad a cookie sobre header Authorization.

        Given: Un usuario con cookie httpOnly válida
        When: El usuario hace request con cookie + header Authorization (ambos)
        Then:
            - Middleware usa token de la cookie (prioridad 1)
            - Header Authorization es ignorado (prioridad 2)
            - Autenticación exitosa
        """
        # Given: Registrar y hacer login (obtener cookie)
        register_payload = RegisterUserRequestDTO(
            email=test_user_data["email"],
            password=test_user_data["password"],
            first_name=test_user_data["first_name"],
            last_name=test_user_data["last_name"],
        )
        await client.post("/api/v1/auth/register", json=register_payload.model_dump())

        login_payload = {
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_response.status_code == 200

        # When: Request con cookie + header Authorization (token diferente/inválido en header)
        # El middleware debería usar la cookie (válida) y ignorar el header (inválido)
        fake_token = "fake_invalid_token_12345"
        response = await client.get(
            "/api/v1/auth/current-user",
            headers={"Authorization": f"Bearer {fake_token}"}
        )

        # Then: Autenticación exitosa (usó cookie, ignoró header inválido)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]

        # Nota: Esto demuestra que la cookie tiene prioridad absoluta.
        # Si el middleware intentara usar el header, fallaría con 401.

    async def test_authentication_fails_without_cookie_and_header(
        self,
        client: AsyncClient,
    ):
        """
        Test: GET /current-user falla cuando NO hay ni cookie ni header.

        Given: Cliente sin autenticación
        When: El usuario hace request sin cookie ni header Authorization
        Then:
            - HTTP 401 Unauthorized
            - Mensaje: "Credenciales de autenticación no proporcionadas"
        """
        # Given: Cliente sin autenticación (sin cookie, sin header)
        # Crear un cliente nuevo sin cookies
        from httpx import AsyncClient as FreshClient
        from main import app

        async with FreshClient(app=app, base_url="http://test") as fresh_client:
            # When: Request a endpoint protegido sin autenticación
            response = await fresh_client.get("/api/v1/auth/current-user")

            # Then: HTTP 401
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert "autenticación" in data["detail"].lower()
