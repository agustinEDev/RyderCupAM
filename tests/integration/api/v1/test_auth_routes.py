import pytest
from httpx import AsyncClient
from fastapi import status

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
            "password": "ValidPass123",
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
            "password": "ValidPass123",
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
        from tests.conftest import create_authenticated_user

        auth_data = await create_authenticated_user(
            client,
            "logout.test@example.com",
            "ValidPass123",
            "Logout",
            "Test"
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
        # FastAPI devuelve 403 cuando falta completamente el header Authorization
        assert response.status_code == status.HTTP_403_FORBIDDEN

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
        Then: Retorna 200 OK y el email se verifica
        """
        # Arrange - Registrar usuario
        user_data = {
            "email": "verify.success@example.com",
            "password": "ValidPass123",
            "first_name": "Verify",
            "last_name": "Success",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener el token de verificación desde la BD (en un escenario real vendría por email)
        # Para tests, necesitamos acceder directamente al repositorio
        from tests.conftest import get_user_by_email
        user = await get_user_by_email(client, user_data["email"])
        verification_token = user.verification_token

        # Act - Verificar email
        verify_data = {"token": verification_token}
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["email_verified"] is True
        assert "verificado" in response_data["message"].lower()

    async def test_verify_email_endpoint_invalid_token(self, client: AsyncClient):
        """
        Test: Verificar email con token inválido
        Given: Un token que no existe
        When: Se llama al endpoint
        Then: Retorna 400 Bad Request
        """
        # Arrange
        verify_data = {"token": "invalid_token_that_does_not_exist"}

        # Act
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "inválido" in response.json()["detail"].lower()

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
            "password": "ValidPass123",
            "first_name": "Already",
            "last_name": "Verified",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener token y verificar primera vez
        from tests.conftest import get_user_by_email
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
