import pytest
from fastapi import status
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, get_user_by_email

# Marcar todos los tests para ejecutarse con asyncio
pytestmark = pytest.mark.asyncio


class TestAuthRoutes:
    """
    Suite de tests de integración para las rutas de autenticación.
    """

    async def test_register_user_successfully(self, client: AsyncClient):
        """
        Verifica que un usuario puede registrarse correctamente a través del endpoint.
        Espera un código de estado 201 Created.
        """
        # Arrange
        user_data = {
            "email": "integration.test@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Integration",
            "last_name": "Test",
        }

        # Act
        response = await client.post("/api/v1/auth/register", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["email"] == user_data["email"]
        assert response_data["first_name"] == user_data["first_name"]
        assert "id" in response_data

    async def test_register_user_fails_if_email_exists(self, client: AsyncClient):
        """
        Verifica que el registro falla con un 409 Conflict si el email ya existe.
        """
        # Arrange: Primero, registrar un usuario.
        user_data = {
            "email": "conflict.test@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Conflict",
            "last_name": "Test",
        }
        first_response = await client.post("/api/v1/auth/register", json=user_data)
        assert first_response.status_code == status.HTTP_201_CREATED

        # Act: Intentar registrarlo de nuevo con el mismo email.
        second_response = await client.post("/api/v1/auth/register", json=user_data)

        # Assert
        assert second_response.status_code == status.HTTP_409_CONFLICT
        assert "ya está registrado" in second_response.json()["detail"]

    async def test_logout_user_successfully(self, client: AsyncClient):
        """
        Verifica que un usuario autenticado puede hacer logout correctamente.
        """
        # Arrange: Crear y autenticar un usuario

        auth_data = await create_authenticated_user(
            client, "logout.test@example.com", "V@l1dP@ss123!", "Logout", "Test"
        )
        token = auth_data["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Act: Hacer logout
        logout_data = {}  # LogoutRequestDTO está vacío en Fase 1
        response = await client.post("/api/v1/auth/logout", json=logout_data, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["message"] == "Logout exitoso"
        assert "logged_out_at" in response_data

    async def test_logout_fails_without_authentication(self, client: AsyncClient):
        """
        Verifica que el logout falla si no se proporciona token de autenticación.
        """
        # Arrange
        logout_data = {}

        # Act: Intentar logout sin autenticación
        response = await client.post("/api/v1/auth/logout", json=logout_data)

        # Assert
        # Con HTTPOnly Cookies, devuelve 401 cuando no hay cookie de autenticación
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_fails_with_invalid_token(self, client: AsyncClient):
        """
        Verifica que el logout falla con un token inválido.
        """
        # Arrange
        invalid_token = "invalid-jwt-token"
        headers = {"Authorization": f"Bearer {invalid_token}"}
        logout_data = {}

        # Act: Intentar logout con token inválido
        response = await client.post("/api/v1/auth/logout", json=logout_data, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_verify_email_endpoint_success(self, client: AsyncClient):
        """
        Test: Verificar email exitosamente
        Given: Un usuario registrado con token de verificación
        When: Se llama al endpoint con el token correcto
        Then: Retorna 200 OK, un JWT y el usuario autenticado con email verificado
        """
        # Arrange - Registrar usuario
        user_data = {
            "email": "verify.success@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Verify",
            "last_name": "Success",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener el token de verificación desde la BD (en un escenario real vendría por email)

        user = await get_user_by_email(client, user_data["email"])
        verification_token = user.verification_token

        # Act - Verificar email
        verify_data = {"token": verification_token}
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        # Nuevo contrato: LoginResponseDTO
        assert "access_token" in response_data
        assert response_data["token_type"] == "bearer"
        assert "user" in response_data
        assert response_data["user"]["email_verified"] is True
        # El mensaje de éxito está en el DTO original, pero ahora solo validamos el JWT y el usuario
        # Si quieres validar el mensaje, puedes agregarlo como campo extra en el DTO o en user

    async def test_verify_email_endpoint_invalid_token(self, client: AsyncClient):
        """
        Test: Verificar email con token inválido
        Given: Un token que no existe
        When: Se llama al endpoint
        Then: Retorna 400 Bad Request con mensaje genérico (seguridad)
        """
        # Arrange
        verify_data = {"token": "invalid_token_that_does_not_exist"}

        # Act
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Verificar mensaje genérico (no revela información específica)
        assert "unable to verify email" in response.json()["detail"].lower()

    async def test_verify_email_endpoint_empty_token(self, client: AsyncClient):
        """
        Test: Verificar email con token vacío
        Given: Un token vacío
        When: Se llama al endpoint
        Then: Retorna 422 Unprocessable Entity (error de validación de Pydantic)
        """
        # Arrange
        verify_data = {"token": ""}

        # Act
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        # FastAPI retorna 422 para errores de validación de Pydantic
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_verify_email_endpoint_already_verified(self, client: AsyncClient):
        """
        Test: Intentar verificar email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta verificar de nuevo
        Then: Retorna 400 Bad Request
        """
        # Arrange - Registrar y verificar usuario
        user_data = {
            "email": "already.verified@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Already",
            "last_name": "Verified",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener token y verificar primera vez

        user = await get_user_by_email(client, user_data["email"])
        verification_token = user.verification_token

        verify_data = {"token": verification_token}
        first_verify = await client.post("/api/v1/auth/verify-email", json=verify_data)
        assert first_verify.status_code == status.HTTP_200_OK

        # Act - Intentar verificar de nuevo con cualquier token
        verify_data_again = {"token": "any_token"}
        response = await client.post("/api/v1/auth/verify-email", json=verify_data_again)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_resend_verification_email_endpoint_success(self, client: AsyncClient):
        """
        Test: Reenviar email de verificación exitosamente
        Given: Un usuario registrado sin verificar
        When: Se llama al endpoint con el email correcto
        Then: Retorna 200 OK y se genera nuevo token
        """
        # Arrange - Registrar usuario
        user_data = {
            "email": "resend.success@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Resend",
            "last_name": "Success",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener el token original

        user_before = await get_user_by_email(client, user_data["email"])
        original_token = user_before.verification_token

        # Act - Reenviar email de verificación (el mock de email está en conftest.py)
        resend_data = {"email": user_data["email"]}
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["email"] == user_data["email"]
        # Mensaje genérico por seguridad
        assert "if the email address exists" in response_data["message"].lower()

        # Verificar que se generó un nuevo token
        user_after = await get_user_by_email(client, user_data["email"])
        assert user_after.verification_token != original_token
        assert user_after.email_verified is False

    async def test_resend_verification_email_endpoint_nonexistent_email(self, client: AsyncClient):
        """
        Test: Reenviar verificación con email no existente
        Given: Un email que no existe en la BD
        When: Se llama al endpoint
        Then: Retorna 200 OK con mensaje genérico (por seguridad, no revela que no existe)
        """
        # Arrange
        resend_data = {"email": "noexiste@example.com"}

        # Act
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        # Por seguridad, siempre retorna 200 OK con mensaje genérico
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "if the email address exists" in response_data["message"].lower()

    async def test_resend_verification_email_endpoint_already_verified(self, client: AsyncClient):
        """
        Test: Reenviar verificación a email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta reenviar verificación
        Then: Retorna 200 OK con mensaje genérico (por seguridad, no revela que ya está verificado)
        """
        # Arrange - Registrar y verificar usuario
        user_data = {
            "email": "verified.resend@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Verified",
            "last_name": "Resend",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Verificar el email
        from tests.conftest import get_user_by_email

        user = await get_user_by_email(client, user_data["email"])
        verification_token = user.verification_token

        verify_data = {"token": verification_token}
        verify_response = await client.post("/api/v1/auth/verify-email", json=verify_data)
        assert verify_response.status_code == status.HTTP_200_OK

        # Act - Intentar reenviar verificación
        resend_data = {"email": user_data["email"]}
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        # Por seguridad, siempre retorna 200 OK con mensaje genérico
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "if the email address exists" in response_data["message"].lower()

    async def test_resend_verification_email_endpoint_invalid_email_format(
        self, client: AsyncClient
    ):
        """
        Test: Reenviar verificación con formato de email inválido
        Given: Un email con formato inválido
        When: Se llama al endpoint
        Then: Retorna 422 Unprocessable Entity
        """
        # Arrange
        resend_data = {"email": "invalid-email-format"}

        # Act
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_login_with_short_password_returns_generic_error(self, client: AsyncClient):
        """
        Verifica que el login con contraseña corta devuelve "Credenciales incorrectas"
        en lugar de revelar información sobre validaciones de contraseña.

        Esto es importante por seguridad: no debemos revelar reglas de validación
        de contraseñas en el endpoint de login.
        """
        # Arrange
        login_data = {
            "email": "any@example.com",
            "password": "short",  # Contraseña de solo 5 caracteres (< 8 requeridos)
        }

        # Act
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        response_data = response.json()
        assert response_data["detail"] == "Credenciales incorrectas"
        # NO debe contener información sobre validación de longitud
        assert "8 characters" not in response_data["detail"]
        assert "min_length" not in response_data["detail"]
        assert "password" not in response_data["detail"].lower()
