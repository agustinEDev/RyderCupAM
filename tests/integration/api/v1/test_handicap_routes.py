"""
Integration tests for Handicap API endpoints
"""

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_handicap_service
from src.modules.user.infrastructure.external.mock_handicap_service import (
    MockHandicapService,
)
from tests.conftest import create_authenticated_user


@pytest.mark.integration
class TestHandicapEndpoints:
    """Tests de integración para los endpoints de hándicap."""

    def setup_method(self):
        """Configurar mocks para cada test."""


        # Mock del servicio de hándicap con datos de prueba
        mock_handicap_service = MockHandicapService(
            handicaps={
                "Rafael Nadal Parera": 8.5,
                "Carlos Alcaraz Garfia": 12.0
            },
            default=None  # Devuelve None para jugadores no configurados
        )

        # Sobreescribir la dependencia para usar el mock
        app.dependency_overrides[get_handicap_service] = lambda: mock_handicap_service

    def teardown_method(self):
        """Limpiar sobreescrituras después de cada test."""
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_handicap_endpoint_success(self, client: AsyncClient):
        """Test: Endpoint de actualización de hándicap funciona correctamente."""
        # Arrange - Crear un usuario autenticado


        auth_data = await create_authenticated_user(
            client,
            "rafa@test.com",
            "P@ssw0rd123!",
            "Rafael",
            "Nadal Parera"
        )

        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint con autenticación
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        # El hándicap debería estar actualizado con el valor del mock
        assert abs(data["handicap"] - 8.5) < 0.01  # Valor configurado en el mock para Rafael Nadal Parera

    @pytest.mark.asyncio
    async def test_update_handicap_endpoint_user_not_found(self, client: AsyncClient):
        """Test: Actualizar hándicap de usuario inexistente devuelve 404."""
        # Arrange - Crear usuario autenticado primero


        auth_data = await create_authenticated_user(
            client,
            "auth@test.com",
            "P@ssw0rd123!",
            "Auth",
            "User"
        )
        token = auth_data["token"]

        non_existent_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": non_existent_id},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_endpoint(self, client: AsyncClient):
        """Test: Endpoint de actualización múltiple funciona correctamente."""
        # Arrange - Crear varios usuarios mediante el endpoint de registro


        # Crear usuario autenticado para hacer la petición
        auth_data = await create_authenticated_user(
            client,
            "admin@test.com",
            "P@ssw0rd123!",
            "Admin",
            "User"
        )
        token = auth_data["token"]

        user1_data = {
            "email": "rafa.multiple@test.com",
            "password": "P@ssw0rd123!",
            "first_name": "Rafael",
            "last_name": "Nadal Parera"
        }
        user2_data = {
            "email": "carlos.multiple@test.com",
            "password": "P@ssw0rd123!",
            "first_name": "Carlos",
            "last_name": "Alcaraz Garfia"
        }

        response1 = await client.post("/api/v1/auth/register", json=user1_data)
        response2 = await client.post("/api/v1/auth/register", json=user2_data)
        assert response1.status_code == 201
        assert response2.status_code == 201

        user_ids = [response1.json()["id"], response2.json()["id"]]

        # Act
        response = await client.post(
            "/api/v1/handicaps/update-multiple",
            json={"user_ids": user_ids},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "message" in data
        # Con el mock configurado, ambos jugadores deberían ser encontrados
        assert data["updated"] == 2
        assert data["not_found"] == 0
        assert data["no_handicap_found"] == 0
        assert data["errors"] == 0
        # Verificar que todos los usuarios están contados en las estadísticas
        total_accounted = data["updated"] + data["not_found"] + data["no_handicap_found"] + data["errors"]
        assert total_accounted == data["total"]

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_empty_list(self, client: AsyncClient):
        """Test: Actualizar lista vacía devuelve estadísticas correctas."""
        # Arrange - Crear usuario autenticado


        auth_data = await create_authenticated_user(
            client,
            "empty@test.com",
            "P@ssw0rd123!",
            "Empty",
            "Test"
        )
        token = auth_data["token"]

        # Act
        response = await client.post(
            "/api/v1/handicaps/update-multiple",
            json={"user_ids": []},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["updated"] == 0

    @pytest.mark.asyncio
    async def test_update_handicap_player_not_in_mock(self, client: AsyncClient):
        """Test: Jugador no configurado en el mock devuelve 404 HandicapNotFoundError."""
        # Arrange - Crear un usuario que no está en el mock


        auth_data = await create_authenticated_user(
            client,
            "unknown@test.com",
            "P@ssw0rd123!",
            "Jugador",
            "Desconocido"
        )
        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint sin manual_handicap
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert - Debe devolver 404 con mensaje descriptivo
        assert response.status_code == 404
        data = response.json()
        assert "No se encontró hándicap en RFEG" in data["detail"]
        assert "Jugador Desconocido" in data["detail"]

    @pytest.mark.asyncio
    async def test_update_handicap_player_not_in_mock_with_manual_fallback(self, client: AsyncClient):
        """Test: Jugador no en mock pero con manual_handicap funciona correctamente."""
        # Arrange - Crear un usuario que no está en el mock


        auth_data = await create_authenticated_user(
            client,
            "manual@test.com",
            "P@ssw0rd123!",
            "Manual",
            "Handicap"
        )
        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint CON manual_handicap
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id, "manual_handicap": 18.5},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert - Debe funcionar usando el manual_handicap
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert abs(data["handicap"] - 18.5) < 0.01

    @pytest.mark.asyncio
    async def test_update_handicap_invalid_uuid(self, client: AsyncClient):
        """Test: UUID inválido devuelve error de validación."""
        # Arrange - Crear usuario autenticado


        auth_data = await create_authenticated_user(
            client,
            "invalid@test.com",
            "P@ssw0rd123!",
            "Invalid",
            "UUID"
        )
        token = auth_data["token"]

        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": "invalid-uuid"},
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert
        assert response.status_code == 422  # Validation error
