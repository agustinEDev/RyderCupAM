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
