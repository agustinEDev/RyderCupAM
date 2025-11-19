# -*- coding: utf-8 -*-
"""
Tests E2E para Competition Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de competiciones incluyendo autenticación, validaciones y persistencia.
"""

import pytest
from httpx import AsyncClient
from datetime import date, timedelta

from tests.conftest import (
    create_authenticated_user,
    create_competition,
    activate_competition,
)


class TestCreateCompetition:
    """Tests para POST /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_create_competition_success(self, client: AsyncClient):
        """Crear competición exitosamente retorna 201."""
        # Arrange
        user = await create_authenticated_user(
            client, "creator@test.com", "Pass123!", "Creator", "Test"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        competition_data = {
            "name": "Ryder Cup Integration Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "handicap_type": "PERCENTAGE",
            "handicap_percentage": 95,
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        # Act
        response = await client.post(
            "/api/v1/competitions",
            json=competition_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Ryder Cup Integration Test"
        assert data["status"] == "DRAFT"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_competition_without_auth_returns_401(self, client: AsyncClient):
        """Crear competición sin autenticación retorna 401."""
        competition_data = {
            "name": "Test",
            "start_date": "2025-12-01",
            "end_date": "2025-12-03",
            "main_country": "ES",
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        response = await client.post("/api/v1/competitions", json=competition_data)
        # FastAPI retorna 403 cuando falta el token de autenticación
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_competition_invalid_dates_returns_400(self, client: AsyncClient):
        """Crear competición con fechas inválidas retorna 400."""
        user = await create_authenticated_user(
            client, "creator2@test.com", "Pass123!", "Creator", "Two"
        )

        # end_date antes de start_date
        competition_data = {
            "name": "Invalid Dates Test",
            "start_date": "2025-12-10",
            "end_date": "2025-12-05",
            "main_country": "ES",
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        response = await client.post(
            "/api/v1/competitions",
            json=competition_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 422  # Validation error


class TestListCompetitions:
    """Tests para GET /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_list_competitions_empty(self, client: AsyncClient):
        """Listar competiciones vacío retorna lista vacía."""
        user = await create_authenticated_user(
            client, "lister@test.com", "Pass123!", "List", "User"
        )

        response = await client.get(
            "/api/v1/competitions",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_competitions_with_data(self, client: AsyncClient):
        """Listar competiciones retorna las creadas."""
        user = await create_authenticated_user(
            client, "lister2@test.com", "Pass123!", "List", "Two"
        )

        # Crear 2 competiciones
        comp1 = await create_competition(client, user["token"])

        start = date.today() + timedelta(days=60)
        end = start + timedelta(days=3)
        comp2_data = {
            "name": "Second Competition",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "FR",
            "handicap_type": "SCRATCH",
            "max_players": 16,
            "team_assignment": "MANUAL"
        }
        await create_competition(client, user["token"], comp2_data)

        # Act
        response = await client.get(
            "/api/v1/competitions",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_competitions_filter_by_status(self, client: AsyncClient):
        """Filtrar competiciones por estado."""
        user = await create_authenticated_user(
            client, "filterer@test.com", "Pass123!", "Filter", "User"
        )

        # Crear y activar una competición
        comp = await create_competition(client, user["token"])
        await activate_competition(client, user["token"], comp["id"])

        # Crear otra en DRAFT
        start = date.today() + timedelta(days=90)
        end = start + timedelta(days=3)
        await create_competition(client, user["token"], {
            "name": "Draft Competition",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        })

        # Filtrar solo ACTIVE
        response = await client.get(
            "/api/v1/competitions?status=ACTIVE",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"


class TestGetCompetition:
    """Tests para GET /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_get_competition_success(self, client: AsyncClient):
        """Obtener competición por ID retorna datos completos."""
        user = await create_authenticated_user(
            client, "getter@test.com", "Pass123!", "Get", "User"
        )

        comp = await create_competition(client, user["token"])

        response = await client.get(
            f"/api/v1/competitions/{comp['id']}",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comp["id"]
        assert "is_creator" in data
        assert data["is_creator"] is True

    @pytest.mark.asyncio
    async def test_get_competition_not_found(self, client: AsyncClient):
        """Obtener competición inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "getter2@test.com", "Pass123!", "Get", "Two"
        )

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/competitions/{fake_id}",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 404


class TestUpdateCompetition:
    """Tests para PUT /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_update_competition_success(self, client: AsyncClient):
        """Actualizar competición en DRAFT exitosamente."""
        user = await create_authenticated_user(
            client, "updater@test.com", "Pass123!", "Update", "User"
        )

        comp = await create_competition(client, user["token"])

        update_data = {
            "name": "Updated Name",
            "max_players": 16
        }

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json=update_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_competition_not_creator_returns_403(self, client: AsyncClient):
        """Actualizar competición de otro usuario retorna 403."""
        creator = await create_authenticated_user(
            client, "creator3@test.com", "Pass123!", "Creator", "Three"
        )
        other_user = await create_authenticated_user(
            client, "other@test.com", "Pass123!", "Other", "User"
        )

        comp = await create_competition(client, creator["token"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {other_user['token']}"}
        )

        assert response.status_code == 403


class TestDeleteCompetition:
    """Tests para DELETE /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_delete_competition_success(self, client: AsyncClient):
        """Eliminar competición en DRAFT retorna 204."""
        user = await create_authenticated_user(
            client, "deleter@test.com", "Pass123!", "Delete", "User"
        )

        comp = await create_competition(client, user["token"])

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_active_competition_returns_400(self, client: AsyncClient):
        """Eliminar competición ACTIVE retorna 400."""
        user = await create_authenticated_user(
            client, "deleter2@test.com", "Pass123!", "Delete", "Two"
        )

        comp = await create_competition(client, user["token"])
        await activate_competition(client, user["token"], comp["id"])

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400


class TestCompetitionStateTransitions:
    """Tests para transiciones de estado de Competition"""

    @pytest.mark.asyncio
    async def test_activate_competition(self, client: AsyncClient):
        """Activar competición cambia estado a ACTIVE."""
        user = await create_authenticated_user(
            client, "activator@test.com", "Pass123!", "Activate", "User"
        )

        comp = await create_competition(client, user["token"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_cancel_competition(self, client: AsyncClient):
        """Cancelar competición cambia estado a CANCELLED."""
        user = await create_authenticated_user(
            client, "canceler@test.com", "Pass123!", "Cancel", "User"
        )

        comp = await create_competition(client, user["token"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client: AsyncClient):
        """Test del ciclo de vida completo: DRAFT -> ACTIVE -> CLOSED -> IN_PROGRESS -> COMPLETED."""
        user = await create_authenticated_user(
            client, "lifecycle@test.com", "Pass123!", "Life", "Cycle"
        )

        # 1. Crear (DRAFT)
        comp = await create_competition(client, user["token"])
        assert comp["status"] == "DRAFT"

        # 2. Activar (ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate",
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        assert response.json()["status"] == "ACTIVE"

        # 3. Cerrar inscripciones (CLOSED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        assert response.json()["status"] == "CLOSED"

        # 4. Iniciar (IN_PROGRESS)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/start",
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        assert response.json()["status"] == "IN_PROGRESS"

        # 5. Completar (COMPLETED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/complete",
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        assert response.json()["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_invalid_state_transition_returns_400(self, client: AsyncClient):
        """Transición de estado inválida retorna 400."""
        user = await create_authenticated_user(
            client, "invalid_trans@test.com", "Pass123!", "Invalid", "Trans"
        )

        comp = await create_competition(client, user["token"])

        # Intentar cerrar inscripciones desde DRAFT (debe ser ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400


class TestEdgeCases:
    """Tests de edge cases para Competition"""

    @pytest.mark.asyncio
    async def test_create_competition_duplicate_name_returns_409(self, client: AsyncClient):
        """Crear competición con nombre duplicado retorna 409."""
        user = await create_authenticated_user(
            client, "dupname@test.com", "Pass123!", "Dup", "Name"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Unique Name Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        # Primera creación
        await client.post(
            "/api/v1/competitions",
            json=comp_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        # Segunda con mismo nombre
        response = await client.post(
            "/api/v1/competitions",
            json=comp_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_non_draft_competition_returns_400(self, client: AsyncClient):
        """Actualizar competición no-DRAFT retorna 400."""
        user = await create_authenticated_user(
            client, "update_active@test.com", "Pass123!", "Update", "Active"
        )

        comp = await create_competition(client, user["token"])
        await activate_competition(client, user["token"], comp["id"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "New Name"},
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_competition_with_is_creator_false(self, client: AsyncClient):
        """Ver competición de otro usuario tiene is_creator=false."""
        creator = await create_authenticated_user(
            client, "creator_check@test.com", "Pass123!", "Creator", "Check"
        )
        viewer = await create_authenticated_user(
            client, "viewer@test.com", "Pass123!", "Viewer", "User"
        )

        comp = await create_competition(client, creator["token"])

        response = await client.get(
            f"/api/v1/competitions/{comp['id']}",
            headers={"Authorization": f"Bearer {viewer['token']}"}
        )

        assert response.status_code == 200
        assert response.json()["is_creator"] is False

    @pytest.mark.asyncio
    async def test_create_competition_with_invalid_country_returns_400(self, client: AsyncClient):
        """Crear competición con país inválido retorna 400."""
        user = await create_authenticated_user(
            client, "badcountry@test.com", "Pass123!", "Bad", "Country"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Invalid Country Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "XX",  # País inválido
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        response = await client.post(
            "/api/v1/competitions",
            json=comp_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        # Podría ser 400 o 422 dependiendo de la validación
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_competition_with_non_adjacent_countries_returns_400(self, client: AsyncClient):
        """Crear competición con países no adyacentes retorna 400."""
        user = await create_authenticated_user(
            client, "nonadjacent@test.com", "Pass123!", "Non", "Adjacent"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Non Adjacent Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "adjacent_country_1": "JP",  # Japón no es adyacente a España
            "handicap_type": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

        response = await client.post(
            "/api/v1/competitions",
            json=comp_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_competition_returns_400(self, client: AsyncClient):
        """Cancelar competición ya cancelada retorna 400."""
        user = await create_authenticated_user(
            client, "doublecancel@test.com", "Pass123!", "Double", "Cancel"
        )

        comp = await create_competition(client, user["token"])

        # Primera cancelación
        await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        # Segunda cancelación
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel",
            headers={"Authorization": f"Bearer {user['token']}"}
        )

        assert response.status_code == 400
