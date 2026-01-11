"""
Tests de integración para Device Routes (API Layer).

Endpoints probados:
- GET /api/v1/users/me/devices - Listar dispositivos activos
- DELETE /api/v1/users/me/devices/{device_id} - Revocar dispositivo

Requiere:
- PostgreSQL corriendo (fixture db_session)
- Usuario autenticado (fixture authenticated_client)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestListUserDevicesEndpoint:
    """Tests de integración para GET /api/v1/users/me/devices"""

    async def test_list_devices_returns_login_device(self, authenticated_client):
        """
        Test: Listar dispositivos incluye el dispositivo del login
        Given: Usuario autenticado (login automáticamente registra dispositivo)
        When: GET /api/v1/users/me/devices
        Then: HTTP 200 con un dispositivo (del login)

        Note (v1.13.0 - Device Fingerprinting):
            El fixture authenticated_client hace login, lo cual automáticamente
            registra el dispositivo. Este test verifica que se liste correctamente.
        """
        # Arrange
        client, _user_data = authenticated_client

        # Act
        response = await client.get("/api/v1/users/me/devices")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["devices"]) == 1  # Login registró 1 dispositivo
        assert data["total_count"] == 1

        # Verificar estructura del dispositivo
        device = data["devices"][0]
        assert "id" in device
        assert "device_name" in device
        assert "ip_address" in device
        assert "last_used_at" in device
        assert "created_at" in device

    async def test_list_devices_requires_authentication(self, client: AsyncClient):
        """
        Test: Listar dispositivos sin autenticación falla
        Given: Cliente NO autenticado
        When: GET /api/v1/users/me/devices
        Then: HTTP 401 Unauthorized
        """
        # Act
        response = await client.get("/api/v1/users/me/devices")

        # Assert
        assert response.status_code == 401

    async def test_list_devices_contains_all_expected_fields(self, authenticated_client):
        """
        Test: Respuesta de listar dispositivos contiene estructura correcta
        Given: Usuario autenticado
        When: GET /api/v1/users/me/devices
        Then: Respuesta contiene 'devices' array y 'total_count'
        """
        # Arrange
        client, _user_data = authenticated_client

        # Act
        response = await client.get("/api/v1/users/me/devices")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total_count" in data
        assert isinstance(data["devices"], list)
        assert isinstance(data["total_count"], int)


@pytest.mark.asyncio
class TestRevokeDeviceEndpoint:
    """Tests de integración para DELETE /api/v1/users/me/devices/{device_id}"""

    async def test_revoke_device_not_found_returns_404(self, authenticated_client):
        """
        Test: Revocar dispositivo inexistente retorna 404
        Given: device_id que no existe
        When: DELETE /api/v1/users/me/devices/{non_existent_id}
        Then: HTTP 404 Not Found
        """
        # Arrange
        client, _user_data = authenticated_client
        from src.modules.user.domain.value_objects.user_device_id import UserDeviceId

        non_existent_id = str(UserDeviceId.generate().value)

        # Act
        response = await client.delete(f"/api/v1/users/me/devices/{non_existent_id}")

        # Assert
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"]

    async def test_revoke_device_requires_authentication(self, client: AsyncClient):
        """
        Test: Revocar dispositivo sin autenticación falla
        Given: Cliente NO autenticado
        When: DELETE /api/v1/users/me/devices/{device_id}
        Then: HTTP 401 Unauthorized
        """
        # Arrange
        from src.modules.user.domain.value_objects.user_device_id import UserDeviceId

        device_id = str(UserDeviceId.generate().value)

        # Act
        response = await client.delete(f"/api/v1/users/me/devices/{device_id}")

        # Assert
        assert response.status_code == 401

    async def test_revoke_device_with_invalid_id_returns_404(self, authenticated_client):
        """
        Test: device_id inválido retorna 404
        Given: device_id que no es UUID válido
        When: DELETE /api/v1/users/me/devices/{invalid_id}
        Then: HTTP 404 (ValueError convertido a 404)
        """
        # Arrange
        client, _user_data = authenticated_client

        # Act
        response = await client.delete("/api/v1/users/me/devices/invalid-uuid-format")

        # Assert
        assert response.status_code == 404
