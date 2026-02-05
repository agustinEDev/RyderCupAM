"""
Tests E2E para Competition Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de competiciones incluyendo autenticación, validaciones y persistencia.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    activate_competition,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
)


class TestCreateCompetition:
    """Tests para POST /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_create_competition_success(self, client: AsyncClient):
        """Crear competición exitosamente retorna 201."""
        # Arrange
        user = await create_authenticated_user(
            client, "creator@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        competition_data = {
            "name": "Ryder Cup Integration Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        # Act
        response = await client.post(
            "/api/v1/competitions", json=competition_data, cookies=user["cookies"]
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
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post("/api/v1/competitions", json=competition_data)
        # Con HTTPOnly Cookies, retorna 401 cuando no hay autenticación
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_competition_invalid_dates_returns_400(self, client: AsyncClient):
        """Crear competición con fechas inválidas retorna 400."""
        user = await create_authenticated_user(
            client, "creator2@test.com", "P@ssw0rd123!", "Creator", "Two"
        )

        # end_date antes de start_date
        competition_data = {
            "name": "Invalid Dates Test",
            "start_date": "2025-12-10",
            "end_date": "2025-12-05",
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=competition_data, cookies=user["cookies"]
        )

        assert response.status_code == 422  # Validation error


class TestListCompetitions:
    """Tests para GET /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_list_competitions_empty(self, client: AsyncClient):
        """Listar competiciones vacío retorna lista vacía."""
        user = await create_authenticated_user(
            client, "lister@test.com", "P@ssw0rd123!", "List", "User"
        )

        response = await client.get("/api/v1/competitions", cookies=user["cookies"])

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_competitions_with_data(self, client: AsyncClient):
        """Listar competiciones retorna las creadas."""
        user = await create_authenticated_user(
            client, "lister2@test.com", "P@ssw0rd123!", "List", "Two"
        )

        # Crear 2 competiciones
        await create_competition(client, user["cookies"])

        start = date.today() + timedelta(days=60)
        end = start + timedelta(days=3)
        comp2_data = {
            "name": "Second Competition",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "FR",
            "play_mode": "SCRATCH",
            "max_players": 16,
            "team_assignment": "MANUAL",
        }
        await create_competition(client, user["cookies"], comp2_data)

        # Act
        response = await client.get("/api/v1/competitions", cookies=user["cookies"])

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_competitions_filter_by_status(self, client: AsyncClient):
        """Filtrar competiciones por estado."""
        user = await create_authenticated_user(
            client, "filterer@test.com", "P@ssw0rd123!", "Filter", "User"
        )

        # Crear y activar una competición
        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        # Crear otra en DRAFT
        start = date.today() + timedelta(days=90)
        end = start + timedelta(days=3)
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Draft Competition",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        # Filtrar solo ACTIVE
        response = await client.get("/api/v1/competitions?status=ACTIVE", cookies=user["cookies"])

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_list_competitions_filter_by_search_name(self, client: AsyncClient):
        """Filtrar competiciones por nombre de búsqueda."""
        user = await create_authenticated_user(
            client, "searcher@test.com", "P@ssw0rd123!", "Search", "User"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        # Crear competiciones
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Ryder Cup 2025",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Open de España",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Ryder Cup Friends",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        # Filtrar por "Ryder"
        response = await client.get(
            "/api/v1/competitions?search_name=Ryder", cookies=user["cookies"]
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "Ryder Cup 2025" in [c["name"] for c in data]
        assert "Ryder Cup Friends" in [c["name"] for c in data]


class TestMyCompetitionsFilter:
    """Tests para el filtro `my_competitions` en GET /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_list_my_competitions_as_creator(self, client: AsyncClient):
        """`my_competitions=true` devuelve solo las competiciones creadas por el usuario."""
        creator = await create_authenticated_user(
            client, "my_creator@test.com", "P@ssw0rd123!", "My", "Creator"
        )
        other_user = await create_authenticated_user(
            client, "other_creator@test.com", "P@ssw0rd123!", "Other", "Creator"
        )

        # Crear competiciones
        await create_competition(client, creator["cookies"])  # Creada por el usuario
        await create_competition(client, other_user["cookies"])  # Creada por otro

        # Act
        response = await client.get(
            "/api/v1/competitions?my_competitions=true", cookies=creator["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["creator_id"] == creator["user"]["id"]

    @pytest.mark.asyncio
    async def test_list_my_competitions_as_enrolled(self, client: AsyncClient):
        """`my_competitions=true` devuelve competiciones en las que el usuario está inscrito."""
        creator = await create_authenticated_user(
            client, "enrolled_creator@test.com", "P@ssw0rd123!", "Enrolled", "Creator"
        )
        enrolled_user = await create_authenticated_user(
            client, "enrolled_user@test.com", "P@ssw0rd123!", "Enrolled", "User"
        )

        # Crear competición y activar
        comp = await create_competition(client, creator["cookies"])
        await activate_competition(client, creator["cookies"], comp["id"])

        # Inscribir usuario
        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            cookies=enrolled_user["cookies"],
        )

        # Act
        response = await client.get(
            "/api/v1/competitions?my_competitions=true",
            cookies=enrolled_user["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == comp["id"]


class TestGetCompetition:
    """Tests para GET /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_get_competition_success(self, client: AsyncClient):
        """Obtener competición por ID retorna datos completos, incluyendo el creador."""
        user = await create_authenticated_user(
            client, "getter@test.com", "P@ssw0rd123!", "Get", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.get(f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"])

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comp["id"]
        assert "is_creator" in data
        assert data["is_creator"] is True
        assert "creator" in data
        assert data["creator"]["id"] == user["user"]["id"]
        assert data["creator"]["first_name"] == "Get"
        assert data["creator"]["last_name"] == "User"

    @pytest.mark.asyncio
    async def test_get_competition_not_found(self, client: AsyncClient):
        """Obtener competición inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "getter2@test.com", "P@ssw0rd123!", "Get", "Two"
        )

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/competitions/{fake_id}", cookies=user["cookies"])

        assert response.status_code == 404


class TestUpdateCompetition:
    """Tests para PUT /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_update_competition_success(self, client: AsyncClient):
        """Actualizar competición en DRAFT exitosamente."""
        user = await create_authenticated_user(
            client, "updater@test.com", "P@ssw0rd123!", "Update", "User"
        )

        comp = await create_competition(client, user["cookies"])

        update_data = {
            "name": "Updated Ryder Cup Name",
            "max_players": 50,
            "team_assignment": "AUTOMATIC",
            "team_1_name": "Team Europe Updated",
        }

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json=update_data,
            cookies=user["cookies"],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Ryder Cup Name"
        assert data["max_players"] == 50
        assert data["team_assignment"] == "AUTOMATIC"
        # team_1_name no está en el response DTO, así que no podemos verificarlo directamente
        # Para verificarlo, necesitaríamos un GET y que el DTO de GET lo incluyera.
        # Por ahora, confiamos en que el cambio se aplicó si el resto funciona.

    @pytest.mark.asyncio
    async def test_update_competition_not_creator_returns_403(self, client: AsyncClient):
        """Actualizar competición de otro usuario retorna 403."""
        creator = await create_authenticated_user(
            client, "creator3@test.com", "P@ssw0rd123!", "Creator", "Three"
        )
        other_user = await create_authenticated_user(
            client, "other@test.com", "P@ssw0rd123!", "Other", "User"
        )

        comp = await create_competition(client, creator["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "Hacked Name"},
            cookies=other_user["cookies"],
        )

        assert response.status_code == 403


class TestDeleteCompetition:
    """Tests para DELETE /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_delete_competition_success(self, client: AsyncClient):
        """Eliminar competición en DRAFT retorna 204."""
        user = await create_authenticated_user(
            client, "deleter@test.com", "P@ssw0rd123!", "Delete", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_active_competition_returns_400(self, client: AsyncClient):
        """Eliminar competición ACTIVE retorna 400."""
        user = await create_authenticated_user(
            client, "deleter2@test.com", "P@ssw0rd123!", "Delete", "Two"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 400


class TestCompetitionStateTransitions:
    """Tests para transiciones de estado de Competition"""

    @pytest.mark.asyncio
    async def test_activate_competition(self, client: AsyncClient):
        """Activar competición cambia estado a ACTIVE."""
        user = await create_authenticated_user(
            client, "activator@test.com", "P@ssw0rd123!", "Activate", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_cancel_competition(self, client: AsyncClient):
        """Cancelar competición cambia estado a CANCELLED."""
        user = await create_authenticated_user(
            client, "canceler@test.com", "P@ssw0rd123!", "Cancel", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client: AsyncClient):
        """Test del ciclo de vida completo: DRAFT -> ACTIVE -> CLOSED -> IN_PROGRESS -> COMPLETED."""
        user = await create_authenticated_user(
            client, "lifecycle@test.com", "P@ssw0rd123!", "Life", "Cycle"
        )

        # 1. Crear (DRAFT)
        comp = await create_competition(client, user["cookies"])
        assert comp["status"] == "DRAFT"

        # 2. Activar (ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )
        assert response.json()["status"] == "ACTIVE"

        # 3. Cerrar inscripciones (CLOSED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )
        assert response.json()["status"] == "CLOSED"

        # 4. Iniciar (IN_PROGRESS)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/start", cookies=user["cookies"]
        )
        assert response.json()["status"] == "IN_PROGRESS"

        # 5. Completar (COMPLETED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/complete", cookies=user["cookies"]
        )
        assert response.json()["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_invalid_state_transition_returns_400(self, client: AsyncClient):
        """Transición de estado inválida retorna 400."""
        user = await create_authenticated_user(
            client, "invalid_trans@test.com", "P@ssw0rd123!", "Invalid", "Trans"
        )

        comp = await create_competition(client, user["cookies"])

        # Intentar cerrar inscripciones desde DRAFT (debe ser ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )

        assert response.status_code == 400


class TestEdgeCases:
    """Tests de edge cases para Competition"""

    @pytest.mark.asyncio
    async def test_create_competition_duplicate_name_returns_409(self, client: AsyncClient):
        """Crear competición con nombre duplicado retorna 409."""
        user = await create_authenticated_user(
            client, "dupname@test.com", "P@ssw0rd123!", "Dup", "Name"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Unique Name Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        # Primera creación
        await client.post("/api/v1/competitions", json=comp_data, cookies=user["cookies"])

        # Segunda con mismo nombre
        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_non_draft_competition_returns_400(self, client: AsyncClient):
        """Actualizar competición no-DRAFT retorna 400."""
        user = await create_authenticated_user(
            client, "update_active@test.com", "P@ssw0rd123!", "Update", "Active"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "New Name"},
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_competition_with_is_creator_false(self, client: AsyncClient):
        """Ver competición de otro usuario tiene is_creator=false."""
        creator = await create_authenticated_user(
            client, "creator_check@test.com", "P@ssw0rd123!", "Creator", "Check"
        )
        viewer = await create_authenticated_user(
            client, "viewer@test.com", "P@ssw0rd123!", "Viewer", "User"
        )

        comp = await create_competition(client, creator["cookies"])

        response = await client.get(f"/api/v1/competitions/{comp['id']}", cookies=viewer["cookies"])

        assert response.status_code == 200
        assert response.json()["is_creator"] is False

    @pytest.mark.asyncio
    async def test_create_competition_with_invalid_country_returns_400(self, client: AsyncClient):
        """Crear competición con país inválido retorna 400."""
        user = await create_authenticated_user(
            client, "badcountry@test.com", "P@ssw0rd123!", "Bad", "Country"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Invalid Country Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "XX",  # País inválido
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        # Podría ser 400 o 422 dependiendo de la validación
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_competition_with_non_adjacent_countries_returns_400(
        self, client: AsyncClient
    ):
        """Crear competición con países no adyacentes retorna 400."""
        user = await create_authenticated_user(
            client, "nonadjacent@test.com", "P@ssw0rd123!", "Non", "Adjacent"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Non Adjacent Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "adjacent_country_1": "JP",  # Japón no es adyacente a España
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_competition_returns_400(self, client: AsyncClient):
        """Cancelar competición ya cancelada retorna 400."""
        user = await create_authenticated_user(
            client, "doublecancel@test.com", "P@ssw0rd123!", "Double", "Cancel"
        )

        comp = await create_competition(client, user["cookies"])

        # Primera cancelación
        await client.post(f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"])

        # Segunda cancelación
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"]
        )

        assert response.status_code == 400


class TestCompetitionGolfCourses:
    """Tests para gestión de campos de golf en competiciones."""

    @pytest.mark.asyncio
    async def test_add_golf_course_to_competition_success(self, client: AsyncClient):
        """Añadir campo de golf aprobado a competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_add_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "golf_creator@test.com", "P@ssw0rd123!", "Golf", "Creator"
        )

        # Crear competición en DRAFT
        comp = await create_competition(client, creator["cookies"])

        # Crear y aprobar campo de golf
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_id"] == golf_course["id"]
        assert data["display_order"] == 1
        assert "added_at" in data

    @pytest.mark.asyncio
    async def test_add_golf_course_not_creator_returns_403(self, client: AsyncClient):
        """Añadir campo por usuario que no es creador retorna 403."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_not_creator@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "comp_owner@test.com", "P@ssw0rd123!", "Owner", "User"
        )
        other_user = await create_authenticated_user(
            client, "other_user@test.com", "P@ssw0rd123!", "Other", "User"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=other_user["cookies"],
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_add_golf_course_not_draft_returns_400(self, client: AsyncClient):
        """Añadir campo a competición ACTIVE retorna 400."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_not_draft@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "active_comp@test.com", "P@ssw0rd123!", "Active", "Comp"
        )

        comp = await create_competition(client, creator["cookies"])
        await activate_competition(client, creator["cookies"], comp["id"])

        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 400
        assert "DRAFT" in response.text

    @pytest.mark.asyncio
    async def test_remove_golf_course_from_competition_success(self, client: AsyncClient):
        """Eliminar campo de golf de competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_remove_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "remove_gc@test.com", "P@ssw0rd123!", "Remove", "GC"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Añadir campo primero
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )

        # Act
        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}/golf-courses/{golf_course['id']}",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_id"] == golf_course["id"]
        assert "removed_at" in data

    @pytest.mark.asyncio
    async def test_remove_golf_course_not_assigned_returns_400(self, client: AsyncClient):
        """Eliminar campo no asociado retorna 400."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_unassigned@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "remove_unassigned@test.com", "P@ssw0rd123!", "Remove", "Unassigned"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act (intentar eliminar sin haber añadido)
        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}/golf-courses/{golf_course['id']}",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 400
        assert "no está" in response.text.lower() or "not" in response.text.lower()

    @pytest.mark.asyncio
    async def test_reorder_golf_courses_success(self, client: AsyncClient):
        """Reordenar campos de golf en competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_reorder@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "reorder_gc@test.com", "P@ssw0rd123!", "Reorder", "GC"
        )

        comp = await create_competition(client, creator["cookies"])

        # Crear y añadir 3 campos de golf
        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        gc3 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc3["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc3["id"]},
            cookies=creator["cookies"],
        )

        # Act - Reordenar en orden inverso
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/golf-courses/reorder",
            json={"golf_course_ids": [gc3["id"], gc2["id"], gc1["id"]]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_count"] == 3
        assert "reordered_at" in data

        # Verificar nuevo orden
        list_response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )
        golf_courses_list = list_response.json()
        assert golf_courses_list[0]["golf_course_id"] == gc3["id"]
        assert golf_courses_list[0]["display_order"] == 1
        assert golf_courses_list[1]["golf_course_id"] == gc2["id"]
        assert golf_courses_list[1]["display_order"] == 2
        assert golf_courses_list[2]["golf_course_id"] == gc1["id"]
        assert golf_courses_list[2]["display_order"] == 3

    @pytest.mark.asyncio
    async def test_reorder_golf_courses_missing_ids_returns_400(self, client: AsyncClient):
        """Reordenar con lista incompleta de IDs retorna 400."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_reorder_missing@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "reorder_missing@test.com", "P@ssw0rd123!", "Reorder", "Missing"
        )

        comp = await create_competition(client, creator["cookies"])

        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )

        # Act - Enviar solo 1 de los 2 IDs
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/golf-courses/reorder",
            json={"golf_course_ids": [gc1["id"]]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 400
        assert "especificar" in response.text.lower() or "expected" in response.text.lower()

    @pytest.mark.asyncio
    async def test_list_golf_courses_success(self, client: AsyncClient):
        """Listar campos de golf de una competición es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_list_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "list_gc@test.com", "P@ssw0rd123!", "List", "GC"
        )

        comp = await create_competition(client, creator["cookies"])

        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )

        # Act
        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        golf_courses = response.json()
        assert len(golf_courses) == 2
        assert golf_courses[0]["golf_course_id"] == gc1["id"]
        assert golf_courses[0]["display_order"] == 1
        assert golf_courses[1]["golf_course_id"] == gc2["id"]
        assert golf_courses[1]["display_order"] == 2

        # Verificar que incluye datos completos del campo
        assert "golf_course" in golf_courses[0]
        assert "name" in golf_courses[0]["golf_course"]
        assert "tees" in golf_courses[0]["golf_course"]
        assert "holes" in golf_courses[0]["golf_course"]

    @pytest.mark.asyncio
    async def test_list_golf_courses_empty_returns_empty_list(self, client: AsyncClient):
        """Listar campos de competición sin campos retorna lista vacía."""
        # Arrange
        creator = await create_authenticated_user(
            client, "list_empty@test.com", "P@ssw0rd123!", "List", "Empty"
        )

        comp = await create_competition(client, creator["cookies"])

        # Act
        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        golf_courses = response.json()
        assert len(golf_courses) == 0
        assert golf_courses == []
