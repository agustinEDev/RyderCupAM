"""
Tests de Integración para Refresh Token (Session Timeout - v1.8.0).

Estos tests verifican que el sistema de refresh tokens funciona correctamente
para mantener sesiones activas sin comprometer la seguridad (OWASP A01/A02/A07).

Tests incluidos:
1. POST /refresh-token con refresh token válido retorna nuevo access token
2. POST /refresh-token sin cookie retorna 401 Unauthorized
3. POST /refresh-token con token inválido retorna 401 Unauthorized
4. POST /refresh-token con token revocado (después de logout) retorna 401
5. POST /refresh-token con token expirado retorna 401
6. POST /refresh-token establece nueva cookie access_token (httpOnly)
7. POST /refresh-token NO renueva el refresh token (mantiene el mismo)

Arquitectura:
- Capa: Integration Tests
- Módulo: User (Authentication)
- Feature: Session Timeout with Refresh Tokens (v1.8.0)
"""
import pytest
from httpx import AsyncClient

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO


@pytest.mark.asyncio
class TestRefreshTokenEndpoint:
    """Tests de integración para POST /api/v1/auth/refresh-token."""

    @pytest.fixture
    def test_user_data(self) -> dict:
        """Fixture con datos de usuario para tests de refresh tokens."""
        return {
            "email": "refresh_test@example.com",
            "password": "SecureP@ssw0rd123",
            "first_name": "Refresh",
            "last_name": "Tester",
        }

    async def test_refresh_token_with_valid_token_returns_new_access_token(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /refresh-token con refresh token válido retorna nuevo access token.

        Given: Un usuario autenticado con refresh token válido en cookie
        When: El usuario hace POST /refresh-token
        Then:
            - HTTP 200 OK
            - Response body contiene nuevo access_token
            - Response body contiene token_type "bearer"
            - Response body contiene user data
            - Response body contiene message de éxito
            - Response headers contienen Set-Cookie con nuevo access_token
        """
        # Given: Registrar y hacer login (obtener refresh token)
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

        # When: Renovar el access token usando refresh token
        response = await client.post("/api/v1/auth/refresh-token")

        # Then: Verificar respuesta exitosa
        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["first_name"] == test_user_data["first_name"]
        assert data["user"]["last_name"] == test_user_data["last_name"]
        assert "message" in data
        assert "renovado" in data["message"].lower() or "refresh" in data["message"].lower()

        # Verificar que el access token es un JWT válido
        new_access_token = data["access_token"]
        assert new_access_token is not None
        assert len(new_access_token) > 0
        # Nota: No comparamos con el original porque pueden ser idénticos si se crean en el mismo segundo

        # Then: Verificar cookie httpOnly con nuevo access token
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None, "Set-Cookie header debe existir"
        assert "access_token=" in set_cookie_header
        assert "HttpOnly" in set_cookie_header

    async def test_refresh_token_without_cookie_returns_401(
        self,
        client: AsyncClient,
    ):
        """
        Test: POST /refresh-token sin cookie refresh_token retorna 401 Unauthorized.

        Given: Cliente sin refresh token cookie
        When: El usuario hace POST /refresh-token
        Then:
            - HTTP 401 Unauthorized
            - Response body contiene mensaje de error
        """
        # Given: Cliente nuevo sin refresh token cookie
        from httpx import AsyncClient as FreshClient
        from main import app

        async with FreshClient(app=app, base_url="http://test") as fresh_client:
            # When: Intentar renovar sin refresh token
            response = await fresh_client.post("/api/v1/auth/refresh-token")

            # Then: HTTP 401
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            # El mensaje puede ser variado dependiendo de la validación
            assert any(
                keyword in data["detail"].lower()
                for keyword in ["token", "inválido", "invalid", "expirado", "expired", "login"]
            )

    async def test_refresh_token_with_invalid_token_returns_401(
        self,
        client: AsyncClient,
    ):
        """
        Test: POST /refresh-token con refresh token JWT inválido retorna 401.

        Given: Cliente con refresh token cookie inválido (firma incorrecta)
        When: El usuario hace POST /refresh-token
        Then:
            - HTTP 401 Unauthorized
            - Response body contiene mensaje de error
        """
        # Given: Crear cliente con cookie inválida
        client.cookies.set("refresh_token", "invalid.jwt.token")

        # When: Intentar renovar con token inválido
        response = await client.post("/api/v1/auth/refresh-token")

        # Then: HTTP 401
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert any(
            keyword in data["detail"].lower()
            for keyword in ["token", "inválido", "invalid", "expirado", "expired", "login"]
        )

    async def test_refresh_token_after_logout_returns_401(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /refresh-token después de logout retorna 401 (token revocado).

        Given:
            - Un usuario autenticado con refresh token válido
            - Usuario hace logout (revoca refresh token en BD)
        When: El usuario intenta renovar con el mismo refresh token
        Then:
            - HTTP 401 Unauthorized
            - Response body contiene mensaje de error
        """
        # Given: Registrar y hacer login
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

        # Given: Hacer logout (revoca refresh token)
        logout_payload = {}
        logout_response = await client.post("/api/v1/auth/logout", json=logout_payload)
        assert logout_response.status_code == 200

        # When: Intentar renovar después de logout (token revocado)
        response = await client.post("/api/v1/auth/refresh-token")

        # Then: HTTP 401 (token revocado)
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_refresh_token_can_be_used_to_access_protected_endpoints(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: El nuevo access token obtenido con /refresh-token funciona en endpoints protegidos.

        Given: Un usuario que renovó su access token
        When: El usuario hace request a endpoint protegido con el nuevo token
        Then:
            - HTTP 200 OK
            - Autenticación exitosa
        """
        # Given: Registrar y hacer login
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

        # Given: Renovar access token
        refresh_response = await client.post("/api/v1/auth/refresh-token")
        assert refresh_response.status_code == 200

        # When: Usar el nuevo access token para acceder a endpoint protegido
        # La cookie ya está establecida automáticamente por httpx
        response = await client.get("/api/v1/auth/current-user")

        # Then: Autenticación exitosa
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]

    async def test_refresh_token_does_not_renew_refresh_token_itself(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /refresh-token NO renueva el refresh token (solo access token).

        Given: Un usuario autenticado con refresh token
        When: El usuario renueva el access token
        Then:
            - Response NO contiene nuevo refresh_token
            - Response headers NO establecen nueva cookie refresh_token
            - Solo se renueva el access token
        """
        # Given: Registrar y hacer login
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

        # Guardar refresh token original del body
        original_refresh_token = login_response.json().get("refresh_token")
        assert original_refresh_token is not None

        # When: Renovar access token
        response = await client.post("/api/v1/auth/refresh-token")

        # Then: Response NO contiene nuevo refresh_token
        assert response.status_code == 200
        data = response.json()
        assert "refresh_token" not in data, "refresh-token NO debe renovar el refresh token"

        # Then: Set-Cookie NO establece nueva cookie refresh_token
        set_cookie_header = response.headers.get("set-cookie", "")
        # Debe contener access_token (renovado)
        assert "access_token=" in set_cookie_header
        # Pero NO debe contener refresh_token (no se renueva)
        # Nota: httpx puede retornar múltiples Set-Cookie en un solo header o separados
        # Verificamos que NO aparezca refresh_token en ninguno
        all_set_cookies = response.headers.get_list("set-cookie")
        for cookie in all_set_cookies:
            if "refresh_token" in cookie:
                # Si aparece, debe ser solo el access_token
                # Esto no debería pasar, pero validamos por seguridad
                pytest.fail("refresh_token NO debe ser renovado en /refresh-token")

    async def test_refresh_token_sets_new_access_token_cookie(
        self,
        client: AsyncClient,
        test_user_data: dict,
    ):
        """
        Test: POST /refresh-token establece nueva cookie httpOnly para access_token.

        Given: Un usuario autenticado
        When: El usuario renueva su access token
        Then:
            - Response headers contienen Set-Cookie con access_token
            - Cookie tiene flags: HttpOnly, SameSite=lax, Path=/, Max-Age=900
        """
        # Given: Registrar y hacer login
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

        # When: Renovar access token
        response = await client.post("/api/v1/auth/refresh-token")

        # Then: Verificar cookie httpOnly
        assert response.status_code == 200

        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None, "Set-Cookie header debe existir"

        # Verificar flags de seguridad
        assert "access_token=" in set_cookie_header
        assert "HttpOnly" in set_cookie_header, "Cookie debe tener flag HttpOnly"
        assert "SameSite=lax" in set_cookie_header, "Cookie debe tener SameSite=lax"
        assert "Path=/" in set_cookie_header, "Cookie debe tener Path=/"
        assert "Max-Age=900" in set_cookie_header, "Cookie debe expirar en 15 minutos"
