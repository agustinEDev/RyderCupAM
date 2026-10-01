"""
Integration tests for Handicap API endpoints
"""

import uuid

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_handicap_service
from src.modules.user.infrastructure.external.mock_handicap_service import (
    MockHandicapService,
)
from tests.conftest import create_admin_user, create_authenticated_user


@pytest.mark.integration
class TestHandicapEndpoints:
    """Tests de integración para los endpoints de hándicap."""

    def setup_method(self):
        """Configurar mocks para cada test."""

        # Mock del servicio de hándicap con datos de prueba
        mock_handicap_service = MockHandicapService(
            handicaps={"Rafael Nadal Parera": 8.5, "Carlos Alcaraz Garfia": 12.0},
            default=None,  # Devuelve None para jugadores no configurados
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
            client, "rafa@test.com", "P@ssw0rd123!", "Rafael", "Nadal Parera"
        )

        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint con autenticación
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        # El hándicap debería estar actualizado con el valor del mock
        assert (
            abs(data["handicap"] - 8.5) < 0.01
        )  # Valor configurado en el mock para Rafael Nadal Parera

    @pytest.mark.asyncio
    async def test_update_handicap_endpoint_user_not_found(self, client: AsyncClient):
        """Test: Un admin que actualiza un usuario inexistente recibe 404.

        Un jugador recibiría 403 sin llegar a buscarlo (#341).
        """
        # Arrange - Un admin: el 404 solo se le da a él (#341)

        auth_data = await create_admin_user(client, "auth@test.com", "P@ssw0rd123!", "Auth", "User")
        token = auth_data["token"]

        non_existent_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": non_existent_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_endpoint(self, client: AsyncClient):
        """Test: Endpoint de actualización múltiple funciona correctamente."""
        # Arrange - Crear varios usuarios mediante el endpoint de registro

        # La actualización masiva es solo del admin (#341)
        auth_data = await create_admin_user(
            client, "admin@test.com", "P@ssw0rd123!", "Admin", "User"
        )
        token = auth_data["token"]

        user1_data = {
            "email": "rafa.multiple@test.com",
            "password": "P@ssw0rd123!",
            "first_name": "Rafael",
            "last_name": "Nadal Parera",
        }
        user2_data = {
            "email": "carlos.multiple@test.com",
            "password": "P@ssw0rd123!",
            "first_name": "Carlos",
            "last_name": "Alcaraz Garfia",
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
            headers={"Authorization": f"Bearer {token}"},
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
        total_accounted = (
            data["updated"] + data["not_found"] + data["no_handicap_found"] + data["errors"]
        )
        assert total_accounted == data["total"]

    @pytest.mark.asyncio
    async def test_update_multiple_handicaps_empty_list(self, client: AsyncClient):
        """Test: Actualizar lista vacía devuelve estadísticas correctas."""
        # Arrange - Crear un admin: la actualización masiva es solo suya (#341)

        auth_data = await create_admin_user(
            client, "empty@test.com", "P@ssw0rd123!", "Empty", "Test"
        )
        token = auth_data["token"]

        # Act
        response = await client.post(
            "/api/v1/handicaps/update-multiple",
            json={"user_ids": []},
            headers={"Authorization": f"Bearer {token}"},
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
            client, "unknown@test.com", "P@ssw0rd123!", "Jugador", "Desconocido"
        )
        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint sin manual_handicap
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert - Debe devolver 404 con mensaje descriptivo
        assert response.status_code == 404
        data = response.json()
        assert "No se encontró hándicap en RFEG" in data["detail"]
        assert "Jugador Desconocido" in data["detail"]

    @pytest.mark.asyncio
    async def test_update_handicap_player_not_in_mock_with_manual_fallback(
        self, client: AsyncClient
    ):
        """Test: Jugador no en mock pero con manual_handicap funciona correctamente."""
        # Arrange - Crear un usuario que no está en el mock

        auth_data = await create_authenticated_user(
            client, "manual@test.com", "P@ssw0rd123!", "Manual", "Handicap"
        )
        user_id = auth_data["user"]["id"]
        token = auth_data["token"]

        # Act - Llamar al endpoint CON manual_handicap
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": user_id, "manual_handicap": 18.5},
            headers={"Authorization": f"Bearer {token}"},
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
            client, "invalid@test.com", "P@ssw0rd123!", "Invalid", "UUID"
        )
        token = auth_data["token"]

        # Act
        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": "invalid-uuid"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 422  # Validation error


@pytest.mark.integration
class TestHandicapEndpointsAuthorization:
    """
    Quién puede cambiar el hándicap de quién (RyderCupAM#341).

    Un jugador solo toca el suyo; el admin, el de cualquiera. Comprobar el permiso
    antes que la existencia del usuario evita que un 404 delate qué ids existen.
    """

    def setup_method(self):
        mock_handicap_service = MockHandicapService(
            handicaps={"Rafael Nadal Parera": 8.5, "Carlos Alcaraz Garfia": 12.0},
            default=None,
        )
        app.dependency_overrides[get_handicap_service] = lambda: mock_handicap_service

    def teardown_method(self):
        app.dependency_overrides.clear()

    @staticmethod
    def _as(client: AsyncClient, data: dict) -> dict:
        """
        Cabecera de quien hace la petición.

        get_current_user prefiere la cookie a la cabecera, y el client se queda la del
        último que inició sesión: sin vaciarla, todas las peticiones irían como él.
        """
        client.cookies.clear()
        return {"Authorization": f"Bearer {data['token']}"}

    async def _handicap_of(self, client: AsyncClient, data: dict) -> float | None:
        response = await client.get("/api/v1/auth/current-user", headers=self._as(client, data))
        assert response.status_code == 200
        return response.json()["handicap"]

    @pytest.mark.asyncio
    async def test_update_manual_on_own_user_succeeds(self, client: AsyncClient):
        """
        Given: Un jugador con sesión
        When: Cambia a mano su propio hándicap
        Then: 200 y el hándicap queda cambiado
        """
        me = await create_authenticated_user(
            client, "self@test.com", "P@ssw0rd123!", "Self", "Player"
        )

        response = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": me["user"]["id"], "handicap": 14.2},
            headers=self._as(client, me),
        )

        assert response.status_code == 200
        assert abs(await self._handicap_of(client, me) - 14.2) < 0.01

    @pytest.mark.asyncio
    async def test_update_manual_on_another_user_is_forbidden(self, client: AsyncClient):
        """
        Given: Dos jugadores sin privilegios
        When: Uno cambia a mano el hándicap del otro
        Then: 403 y el hándicap del otro no cambia
        """
        victim = await create_authenticated_user(
            client, "victim@test.com", "P@ssw0rd123!", "Victim", "Player"
        )
        before = await self._handicap_of(client, victim)
        attacker = await create_authenticated_user(
            client, "attacker@test.com", "P@ssw0rd123!", "Attacker", "Player"
        )

        response = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": victim["user"]["id"], "handicap": 36.0},
            headers=self._as(client, attacker),
        )

        assert response.status_code == 403
        assert await self._handicap_of(client, victim) == before

    @pytest.mark.asyncio
    async def test_update_manual_on_unknown_id_is_forbidden_not_not_found(
        self, client: AsyncClient
    ):
        """
        Given: Un jugador sin privilegios
        When: Cambia a mano el hándicap de un id que no existe
        Then: 403, no 404: la respuesta no dice si el id existe
        """
        me = await create_authenticated_user(
            client, "probe@test.com", "P@ssw0rd123!", "Probe", "Player"
        )

        response = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": str(uuid.uuid4()), "handicap": 10.0},
            headers=self._as(client, me),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_manual_by_admin_on_another_user_succeeds(self, client: AsyncClient):
        """
        Given: Un admin y un jugador
        When: El admin cambia a mano el hándicap del jugador
        Then: 200 y el hándicap del jugador queda cambiado
        """
        player = await create_authenticated_user(
            client, "managed@test.com", "P@ssw0rd123!", "Managed", "Player"
        )
        admin = await create_admin_user(client, "boss@test.com", "P@ssw0rd123!", "Boss", "Admin")

        response = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": player["user"]["id"], "handicap": 22.4},
            headers=self._as(client, admin),
        )

        assert response.status_code == 200
        assert abs(await self._handicap_of(client, player) - 22.4) < 0.01

    @pytest.mark.asyncio
    async def test_update_manual_by_admin_on_unknown_id_is_not_found(self, client: AsyncClient):
        """
        Given: Un admin
        When: Cambia a mano el hándicap de un id que no existe
        Then: 404
        """
        admin = await create_admin_user(client, "boss2@test.com", "P@ssw0rd123!", "Boss", "Admin")

        response = await client.post(
            "/api/v1/handicaps/update-manual",
            json={"user_id": str(uuid.uuid4()), "handicap": 10.0},
            headers=self._as(client, admin),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_from_rfeg_on_another_user_is_forbidden(self, client: AsyncClient):
        """
        Given: Dos jugadores sin privilegios
        When: Uno pide a la RFEG el hándicap del otro, con manual_handicap de respaldo
        Then: 403 y el hándicap del otro no cambia
        """
        victim = await create_authenticated_user(
            client, "rafa.victim@test.com", "P@ssw0rd123!", "Rafael", "Nadal Parera"
        )
        before = await self._handicap_of(client, victim)
        attacker = await create_authenticated_user(
            client, "rfeg.attacker@test.com", "P@ssw0rd123!", "Attacker", "Player"
        )

        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": victim["user"]["id"], "manual_handicap": 36.0},
            headers=self._as(client, attacker),
        )

        assert response.status_code == 403
        assert await self._handicap_of(client, victim) == before

    @pytest.mark.asyncio
    async def test_update_from_rfeg_by_admin_on_another_user_succeeds(self, client: AsyncClient):
        """
        Given: Un admin y un jugador que la RFEG conoce
        When: El admin pide a la RFEG el hándicap del jugador
        Then: 200 con el hándicap de la RFEG
        """
        player = await create_authenticated_user(
            client, "rafa.admin@test.com", "P@ssw0rd123!", "Rafael", "Nadal Parera"
        )
        admin = await create_admin_user(client, "boss3@test.com", "P@ssw0rd123!", "Boss", "Admin")

        response = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": player["user"]["id"]},
            headers=self._as(client, admin),
        )

        assert response.status_code == 200
        assert abs(response.json()["handicap"] - 8.5) < 0.01

    @pytest.mark.asyncio
    async def test_update_multiple_by_player_is_forbidden(self, client: AsyncClient):
        """
        Given: Un jugador sin privilegios
        When: Pide la actualización masiva, aunque sea solo sobre sí mismo
        Then: 403
        """
        me = await create_authenticated_user(
            client, "rafa.bulk@test.com", "P@ssw0rd123!", "Rafael", "Nadal Parera"
        )

        response = await client.post(
            "/api/v1/handicaps/update-multiple",
            json={"user_ids": [me["user"]["id"]]},
            headers=self._as(client, me),
        )

        assert response.status_code == 403


@pytest.mark.integration
class TestRefreshMineEndpoint:
    """
    POST /api/v1/handicaps/refresh-mine (RyderCupAM#340).

    El refresco que antes hacía el login, ahora aparte: el frontend lo pide
    después de entrar, y el login ya no espera a la RFEG.
    """

    def teardown_method(self):
        app.dependency_overrides.clear()

    @staticmethod
    def _rfeg_que_devuelve(handicap: float | None) -> None:
        servicio = MockHandicapService(handicaps={"Rafael Nadal Parera": handicap}, default=None)
        app.dependency_overrides[get_handicap_service] = lambda: servicio

    @pytest.mark.asyncio
    async def test_sin_sesion_no_se_puede(self, client: AsyncClient):
        """R1: sin sesión, 401."""
        response = await client.post("/api/v1/handicaps/refresh-mine")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_un_espanol_que_la_rfeg_encuentra_queda_actualizado(self, client: AsyncClient):
        """
        R2: español, la RFEG lo encuentra -> 200 con el hándicap y sin pedírselo.

        Al registrarse la RFEG todavía no lo tiene (si no, quedaría actualizado
        hoy y el refresco no llegaría a preguntar); después sí.
        """
        # Arrange
        self._rfeg_que_devuelve(None)
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "rafa.es@test.com",
                "password": "P@ssw0rd123!",
                "first_name": "Rafael",
                "last_name": "Nadal Parera",
                "country_code": "ES",
            },
            headers={"X-Test-Client-ID": f"register-{uuid.uuid4()}"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "rafa.es@test.com", "password": "P@ssw0rd123!"},
            headers={"X-Test-Client-ID": f"login-{uuid.uuid4()}"},
        )
        assert login.status_code == 200
        assert "needs_handicap" not in login.json()
        token = login.json()["access_token"]
        client.cookies.clear()
        self._rfeg_que_devuelve(8.5)

        # Act
        response = await client.post(
            "/api/v1/handicaps/refresh-mine",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 200
        assert response.json() == {"needs_handicap": False, "handicap": 8.5}
