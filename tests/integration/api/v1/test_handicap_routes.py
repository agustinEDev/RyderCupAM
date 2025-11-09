"""
Integration tests for Handicap API endpoints
"""

import pytest
from httpx import AsyncClient
from src.modules.user.domain.entities.user import User


@pytest.mark.integration
class TestHandicapEndpoints:
    """Tests de integración para los endpoints de hándicap."""

    @pytest.mark.asyncio
    async def test_update_handicap_endpoint_success(self, client: AsyncClient):
        """Test: Endpoint de actualización de hándicap funciona correctamente."""
        # Arrange - Crear un usuario primero mediante el endpoint de registro
        user_data = {
            "email": "rafa@test.com",
            "password": "Pass123!",
            "first_name": "Rafael",
            "last_name": "Nadal Parera"
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == 201
        user_id = register_response.json()["id"]

        # Act - Llamar al endpoint (esto hará una llamada real a la RFEG)
        # NOTA: Este test puede fallar si la RFEG no está disponible
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        # El hándicap debería estar actualizado (o None si RFEG no lo encuentra)
        assert "handicap" in data

    @pytest.mark.asyncio
    async def test_update_handicap_endpoint_user_not_found(self, client: AsyncClient):
        """Test: Actualizar hándicap de usuario inexistente devuelve 404."""
        # Arrange
        non_existent_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": non_existent_id}
        )

        # Assert
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_endpoint(self, client: AsyncClient):
        """Test: Endpoint de actualización múltiple funciona correctamente."""
        # Arrange - Crear varios usuarios mediante el endpoint de registro
        user1_data = {
            "email": "rafa.multiple@test.com",
            "password": "Pass123!",
            "first_name": "Rafael",
            "last_name": "Nadal Parera"
        }
        user2_data = {
            "email": "carlos.multiple@test.com",
            "password": "Pass123!",
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
            json={"user_ids": user_ids}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "message" in data
        # Puede que updated sea 0, 1 o 2 dependiendo de si RFEG encuentra los jugadores
        assert data["updated"] + data["not_found"] + data["errors"] == 2

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_empty_list(self, client: AsyncClient):
        """Test: Actualizar lista vacía devuelve estadísticas correctas."""
        # Act
        response = await client.post(
            "/api/v1/handicaps/update-multiple",
            json={"user_ids": []}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["updated"] == 0

    @pytest.mark.asyncio
    async def test_update_handicap_invalid_uuid(self, client: AsyncClient):
        """Test: UUID inválido devuelve error de validación."""
        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": "invalid-uuid"}
        )

        # Assert
        assert response.status_code == 422  # Validation error
