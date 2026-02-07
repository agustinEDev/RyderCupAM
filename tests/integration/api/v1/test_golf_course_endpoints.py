"""
Tests E2E para Golf Course Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de campos de golf incluyendo autenticación, validaciones, approval workflow
y persistencia.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import (
    approve_golf_course,
    create_authenticated_user,
    create_golf_course,
)


class TestRequestGolfCourse:
    """Tests para POST /api/v1/golf-courses/request"""

    @pytest.mark.asyncio
    async def test_request_golf_course_success(self, client: AsyncClient):
        """Solicitar campo exitosamente retorna 201 con estado PENDING_APPROVAL."""
        # Arrange
        user = await create_authenticated_user(
            client, "creator@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        golf_course_data = {
            "name": "Real Club de Golf El Prat",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Amarillo",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                },
                {
                    "identifier": "Blanco",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.2,
                    "slope_rating": 128,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        # Act
        response = await client.post(
            "/api/v1/golf-courses/request", json=golf_course_data, cookies=user["cookies"]
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Real Club de Golf El Prat"
        assert data["approval_status"] == "PENDING_APPROVAL"
        assert data["country_code"] == "ES"
        assert data["course_type"] == "STANDARD_18"
        assert "id" in data
        assert len(data["tees"]) == 2  # 2 tees: Amarillo y Blanco
        assert len(data["holes"]) == 18

    @pytest.mark.asyncio
    async def test_request_golf_course_without_auth_returns_401(self, client: AsyncClient):
        """Solicitar campo sin autenticación retorna 401."""
        golf_course_data = {
            "name": "Test Course",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Amarillo",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.post("/api/v1/golf-courses/request", json=golf_course_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_request_golf_course_invalid_country_returns_400(self, client: AsyncClient):
        """Solicitar campo con país inválido retorna 400."""
        user = await create_authenticated_user(
            client, "creator2@test.com", "P@ssw0rd123!", "Creator", "Two"
        )

        golf_course_data = {
            "name": "Invalid Country Course",
            "country_code": "XX",  # País inexistente
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Amarillo",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                },
                {
                    "identifier": "Blanco",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.2,
                    "slope_rating": 128,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.post(
            "/api/v1/golf-courses/request", json=golf_course_data, cookies=user["cookies"]
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_request_golf_course_duplicate_stroke_index_returns_400(
        self, client: AsyncClient
    ):
        """Solicitar campo con stroke index duplicados retorna 400."""
        user = await create_authenticated_user(
            client, "creator3@test.com", "P@ssw0rd123!", "Creator", "Three"
        )

        golf_course_data = {
            "name": "Duplicate Stroke Index Course",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Amarillo",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                },
                {
                    "identifier": "Blanco",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.2,
                    "slope_rating": 128,
                    "par": 72,
                },
            ],
            "holes": [
                {"hole_number": i, "par": 4, "stroke_index": 1}  # Todos tienen stroke_index=1
                for i in range(1, 19)
            ],
        }

        response = await client.post(
            "/api/v1/golf-courses/request", json=golf_course_data, cookies=user["cookies"]
        )

        assert response.status_code == 400


class TestGetGolfCourseById:
    """Tests para GET /api/v1/golf-courses/{id}"""

    @pytest.mark.asyncio
    async def test_get_approved_golf_course_by_any_user(self, client: AsyncClient):
        """Cualquier usuario autenticado puede ver campos aprobados."""
        # Arrange: Creator solicita campo
        creator = await create_authenticated_user(
            client, "creator4@test.com", "P@ssw0rd123!", "Creator", "Four"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Admin aprueba el campo
        admin = await create_authenticated_user(
            client, "admin@test.com", "AdminPass123!", "Admin", "User"
        )

        # Hacer admin al usuario (directamente en BD para test)
        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Regular user intenta ver el campo aprobado
        regular_user = await create_authenticated_user(
            client, "regular@test.com", "RegularPass123!", "Regular", "User"
        )

        # Act
        response = await client.get(
            f"/api/v1/golf-courses/{golf_course['id']}", cookies=regular_user["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == golf_course["id"]
        assert data["approval_status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_get_pending_golf_course_as_creator(self, client: AsyncClient):
        """Creator puede ver su propio campo pendiente."""
        # Arrange
        creator = await create_authenticated_user(
            client, "creator5@test.com", "P@ssw0rd123!", "Creator", "Five"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act
        response = await client.get(
            f"/api/v1/golf-courses/{golf_course['id']}", cookies=creator["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == golf_course["id"]
        assert data["approval_status"] == "PENDING_APPROVAL"

    @pytest.mark.asyncio
    async def test_get_pending_golf_course_as_other_user_returns_403(self, client: AsyncClient):
        """Otro usuario no puede ver campo pendiente de otro creator."""
        # Arrange
        creator = await create_authenticated_user(
            client, "creator6@test.com", "P@ssw0rd123!", "Creator", "Six"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        other_user = await create_authenticated_user(
            client, "other@test.com", "OtherPass123!", "Other", "User"
        )

        # Act
        response = await client.get(
            f"/api/v1/golf-courses/{golf_course['id']}", cookies=other_user["cookies"]
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_golf_course_not_found_returns_404(self, client: AsyncClient):
        """Buscar campo inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "user@test.com", "UserPass123!", "Test", "User"
        )

        fake_id = "00000000-0000-0000-0000-000000000000"

        response = await client.get(f"/api/v1/golf-courses/{fake_id}", cookies=user["cookies"])

        assert response.status_code == 404


class TestListGolfCourses:
    """Tests para GET /api/v1/golf-courses"""

    @pytest.mark.asyncio
    async def test_list_approved_golf_courses(self, client: AsyncClient):
        """Listar campos sin filtros retorna solo aprobados."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin2@test.com", "AdminPass123!", "Admin", "Two"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin2@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        # Creator solicita 2 campos
        creator = await create_authenticated_user(
            client, "creator7@test.com", "P@ssw0rd123!", "Creator", "Seven"
        )
        gc1 = await create_golf_course(client, creator["cookies"])
        gc2 = await create_golf_course(client, creator["cookies"])

        # Admin aprueba solo el primero
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        # Act: Regular user lista campos
        regular_user = await create_authenticated_user(
            client, "regular2@test.com", "RegularPass123!", "Regular", "Two"
        )
        response = await client.get("/api/v1/golf-courses", cookies=regular_user["cookies"])

        # Assert: Solo debe ver el aprobado
        assert response.status_code == 200
        data = response.json()
        assert "golf_courses" in data
        golf_courses = data["golf_courses"]

        # Buscar el campo aprobado en la lista
        approved_ids = [gc["id"] for gc in golf_courses]
        assert gc1["id"] in approved_ids
        assert gc2["id"] not in approved_ids  # Pendiente no debe aparecer

    @pytest.mark.asyncio
    async def test_list_golf_courses_without_auth_returns_401(self, client: AsyncClient):
        """Listar campos sin autenticación retorna 401."""
        response = await client.get("/api/v1/golf-courses")
        assert response.status_code == 401


class TestListPendingGolfCourses:
    """Tests para GET /api/v1/golf-courses/admin/pending"""

    @pytest.mark.asyncio
    async def test_admin_list_pending_golf_courses(self, client: AsyncClient):
        """Admin puede listar campos pendientes."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin3@test.com", "AdminPass123!", "Admin", "Three"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin3@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        # Creator solicita campo
        creator = await create_authenticated_user(
            client, "creator8@test.com", "P@ssw0rd123!", "Creator", "Eight"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act: Admin lista pendientes
        response = await client.get("/api/v1/golf-courses/admin/pending", cookies=admin["cookies"])

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "golf_courses" in data
        pending_ids = [gc["id"] for gc in data["golf_courses"]]
        assert golf_course["id"] in pending_ids

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_pending_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede listar pendientes."""
        user = await create_authenticated_user(
            client, "regular3@test.com", "RegularPass123!", "Regular", "Three"
        )

        response = await client.get("/api/v1/golf-courses/admin/pending", cookies=user["cookies"])

        assert response.status_code == 403


class TestApproveGolfCourse:
    """Tests para PUT /api/v1/golf-courses/admin/{id}/approve"""

    @pytest.mark.asyncio
    async def test_admin_approve_golf_course_success(self, client: AsyncClient):
        """Admin puede aprobar campo pendiente."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin4@test.com", "AdminPass123!", "Admin", "Four"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin4@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        # Creator solicita campo
        creator = await create_authenticated_user(
            client, "creator9@test.com", "P@ssw0rd123!", "Creator", "Nine"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act: Admin aprueba
        response = await client.put(
            f"/api/v1/golf-courses/admin/{golf_course['id']}/approve", cookies=admin["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["golf_course"]["approval_status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_non_admin_cannot_approve_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede aprobar campos."""
        creator = await create_authenticated_user(
            client, "creator10@test.com", "P@ssw0rd123!", "Creator", "Ten"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        other_user = await create_authenticated_user(
            client, "other2@test.com", "OtherPass123!", "Other", "Two"
        )

        response = await client.put(
            f"/api/v1/golf-courses/admin/{golf_course['id']}/approve", cookies=other_user["cookies"]
        )

        assert response.status_code == 403


class TestRejectGolfCourse:
    """Tests para PUT /api/v1/golf-courses/admin/{id}/reject"""

    @pytest.mark.asyncio
    async def test_admin_reject_golf_course_success(self, client: AsyncClient):
        """Admin puede rechazar campo pendiente con razón."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin5@test.com", "AdminPass123!", "Admin", "Five"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin5@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        # Creator solicita campo
        creator = await create_authenticated_user(
            client, "creator11@test.com", "P@ssw0rd123!", "Creator", "Eleven"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act: Admin rechaza
        reason = "Los datos del campo no coinciden con la información oficial"
        response = await client.put(
            f"/api/v1/golf-courses/admin/{golf_course['id']}/reject",
            params={"reason": reason},
            cookies=admin["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["golf_course"]["approval_status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_admin_reject_without_reason_returns_422(self, client: AsyncClient):
        """Rechazar sin razón retorna 422 (validation error)."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin6@test.com", "AdminPass123!", "Admin", "Six"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin6@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        # Creator solicita campo
        creator = await create_authenticated_user(
            client, "creator12@test.com", "P@ssw0rd123!", "Creator", "Twelve"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act: Admin intenta rechazar sin razón
        response = await client.put(
            f"/api/v1/golf-courses/admin/{golf_course['id']}/reject", cookies=admin["cookies"]
        )

        # Assert: Debe fallar por falta de parámetro requerido
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_cannot_reject_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede rechazar campos."""
        creator = await create_authenticated_user(
            client, "creator13@test.com", "P@ssw0rd123!", "Creator", "Thirteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        other_user = await create_authenticated_user(
            client, "other3@test.com", "OtherPass123!", "Other", "Three"
        )

        response = await client.put(
            f"/api/v1/golf-courses/admin/{golf_course['id']}/reject",
            params={"reason": "Test rejection reason text here"},
            cookies=other_user["cookies"],
        )

        assert response.status_code == 403


class TestCreateDirectGolfCourse:
    """Tests para POST /api/v1/golf-courses/admin (creación directa Admin)"""

    @pytest.mark.asyncio
    async def test_admin_create_direct_golf_course_success(self, client: AsyncClient):
        """Admin puede crear campo directamente en estado APPROVED."""
        # Arrange: Crear admin
        admin = await create_authenticated_user(
            client, "admin7@test.com", "AdminPass123!", "Admin", "Seven"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin7@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        golf_course_data = {
            "name": "Admin Direct Golf Club",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Blanco",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 73.0,
                    "slope_rating": 135,
                    "par": 72,
                },
                {
                    "identifier": "Amarillo",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 71.0,
                    "slope_rating": 130,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        # Act
        response = await client.post(
            "/api/v1/golf-courses/admin", json=golf_course_data, cookies=admin["cookies"]
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "golf_course" in data
        assert data["golf_course"]["name"] == "Admin Direct Golf Club"
        assert data["golf_course"]["approval_status"] == "APPROVED"
        assert data["message"] == "Golf course created successfully (APPROVED)"

    @pytest.mark.asyncio
    async def test_non_admin_cannot_create_direct_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede crear campos directamente."""
        user = await create_authenticated_user(
            client, "regular4@test.com", "RegularPass123!", "Regular", "Four"
        )

        golf_course_data = {
            "name": "Non-Admin Attempt",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Blanco",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 73.0,
                    "slope_rating": 135,
                    "par": 72,
                },
                {
                    "identifier": "Amarillo",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 71.0,
                    "slope_rating": 130,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.post(
            "/api/v1/golf-courses/admin", json=golf_course_data, cookies=user["cookies"]
        )

        assert response.status_code == 403


class TestUpdateGolfCourse:
    """Tests para PUT /api/v1/golf-courses/{id} (update con clone logic)"""

    @pytest.mark.asyncio
    async def test_admin_updates_approved_course_in_place(self, client: AsyncClient):
        """Admin actualiza campo APPROVED in-place sin crear clone."""
        # Arrange: Crear admin y aprobar campo
        admin = await create_authenticated_user(
            client, "admin8@test.com", "AdminPass123!", "Admin", "Eight"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin8@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator14@test.com", "P@ssw0rd123!", "Creator", "Fourteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act: Admin actualiza el campo
        update_data = {
            "name": "Updated by Admin",
            "country_code": "FR",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Blanc",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 74.0,
                    "slope_rating": 138,
                    "par": 72,
                },
                {
                    "identifier": "Jaune",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 72.0,
                    "slope_rating": 133,
                    "par": 72,
                },
            ],
            "holes": [
                {"hole_number": i, "par": 4 if i <= 12 else 3, "stroke_index": i}
                for i in range(1, 19)
            ],
        }

        response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}", json=update_data, cookies=admin["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["golf_course"]["name"] == "Updated by Admin"
        assert data["golf_course"]["country_code"] == "FR"
        assert data["golf_course"]["approval_status"] == "APPROVED"
        assert data["pending_update"] is None  # NO clone
        assert "admin" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_creator_editing_approved_creates_clone(self, client: AsyncClient):
        """Creator editando campo APPROVED crea clone PENDING."""
        # Arrange: Crear admin y aprobar campo del creator
        admin = await create_authenticated_user(
            client, "admin9@test.com", "AdminPass123!", "Admin", "Nine"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin9@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator15@test.com", "P@ssw0rd123!", "Creator", "Fifteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act: Creator actualiza su propio campo APPROVED
        update_data = {
            "name": "Updated by Creator",
            "country_code": "IT",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Bianco",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 73.5,
                    "slope_rating": 136,
                    "par": 72,
                },
                {
                    "identifier": "Giallo",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 71.5,
                    "slope_rating": 131,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        # Original sin cambios
        assert data["golf_course"]["name"] == golf_course["name"]
        assert data["golf_course"]["approval_status"] == "APPROVED"
        assert data["golf_course"]["is_pending_update"] is True
        # Clone creado
        assert data["pending_update"] is not None
        assert data["pending_update"]["name"] == "Updated by Creator"
        assert data["pending_update"]["country_code"] == "IT"
        assert data["pending_update"]["approval_status"] == "PENDING_APPROVAL"
        assert data["pending_update"]["original_golf_course_id"] == golf_course["id"]

    @pytest.mark.asyncio
    async def test_creator_editing_pending_updates_in_place(self, client: AsyncClient):
        """Creator editando su campo PENDING actualiza in-place."""
        # Arrange
        creator = await create_authenticated_user(
            client, "creator16@test.com", "P@ssw0rd123!", "Creator", "Sixteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        # Act: Creator edita su campo PENDING
        update_data = {
            "name": "Updated Pending Course",
            "country_code": "PT",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Branco",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.8,
                    "slope_rating": 134,
                    "par": 72,
                },
                {
                    "identifier": "Amarelo",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.8,
                    "slope_rating": 129,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["golf_course"]["name"] == "Updated Pending Course"
        assert data["golf_course"]["country_code"] == "PT"
        assert data["golf_course"]["approval_status"] == "PENDING_APPROVAL"
        assert data["pending_update"] is None  # NO clone

    @pytest.mark.asyncio
    async def test_non_owner_cannot_update_returns_403(self, client: AsyncClient):
        """Usuario no-owner no puede actualizar campo de otro."""
        creator = await create_authenticated_user(
            client, "creator17@test.com", "P@ssw0rd123!", "Creator", "Seventeen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])

        other_user = await create_authenticated_user(
            client, "other4@test.com", "OtherPass123!", "Other", "Four"
        )

        update_data = {
            "name": "Malicious Update",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "White",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.0,
                    "slope_rating": 130,
                    "par": 72,
                },
                {
                    "identifier": "Yellow",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.0,
                    "slope_rating": 125,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=other_user["cookies"],
        )

        assert response.status_code == 403


class TestApproveUpdateGolfCourse:
    """Tests para PUT /api/v1/golf-courses/admin/{clone_id}/approve-update"""

    @pytest.mark.asyncio
    async def test_admin_approve_update_applies_changes_to_original(self, client: AsyncClient):
        """Admin puede aprobar clone y aplicar cambios al original."""
        # Arrange: Crear admin y aprobar campo inicial
        admin = await create_authenticated_user(
            client, "admin10@test.com", "AdminPass123!", "Admin", "Ten"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin10@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator18@test.com", "P@ssw0rd123!", "Creator", "Eighteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Creator crea clone editando campo APPROVED
        update_data = {
            "name": "Clone to Approve",
            "country_code": "DE",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Weiß",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 74.5,
                    "slope_rating": 140,
                    "par": 72,
                },
                {
                    "identifier": "Gelb",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 72.5,
                    "slope_rating": 135,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        update_response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )
        clone_id = update_response.json()["pending_update"]["id"]

        # Act: Admin aprueba el clone
        response = await client.put(
            f"/api/v1/golf-courses/admin/{clone_id}/approve-update", cookies=admin["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["updated_golf_course"]["name"] == "Clone to Approve"
        assert data["updated_golf_course"]["country_code"] == "DE"
        assert data["updated_golf_course"]["approval_status"] == "APPROVED"
        assert data["updated_golf_course"]["is_pending_update"] is False
        assert data["applied_changes_from"] == clone_id

    @pytest.mark.asyncio
    async def test_non_admin_cannot_approve_update_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede aprobar updates."""
        # Arrange: Crear campo APPROVED y luego clone
        admin = await create_authenticated_user(
            client, "admin11@test.com", "AdminPass123!", "Admin", "Eleven"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin11@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator19@test.com", "P@ssw0rd123!", "Creator", "Nineteen"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Creator crea clone
        update_data = {
            "name": "Clone Attempt",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "White",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.0,
                    "slope_rating": 130,
                    "par": 72,
                },
                {
                    "identifier": "Yellow",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.0,
                    "slope_rating": 125,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        update_response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )
        clone_id = update_response.json()["pending_update"]["id"]

        # Act: Non-admin intenta aprobar
        other_user = await create_authenticated_user(
            client, "other5@test.com", "OtherPass123!", "Other", "Five"
        )

        response = await client.put(
            f"/api/v1/golf-courses/admin/{clone_id}/approve-update", cookies=other_user["cookies"]
        )

        # Assert
        assert response.status_code == 403


class TestRejectUpdateGolfCourse:
    """Tests para PUT /api/v1/golf-courses/admin/{clone_id}/reject-update"""

    @pytest.mark.asyncio
    async def test_admin_reject_update_deletes_clone(self, client: AsyncClient):
        """Admin puede rechazar clone y eliminarlo."""
        # Arrange: Crear admin y aprobar campo inicial
        admin = await create_authenticated_user(
            client, "admin12@test.com", "AdminPass123!", "Admin", "Twelve"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin12@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator20@test.com", "P@ssw0rd123!", "Creator", "Twenty"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Creator crea clone editando campo APPROVED
        update_data = {
            "name": "Clone to Reject",
            "country_code": "ES",  # Usar ES en lugar de NL (asegura que existe en BD)
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "Wit",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 73.0,
                    "slope_rating": 133,
                    "par": 72,
                },
                {
                    "identifier": "Geel",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 71.0,
                    "slope_rating": 128,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        update_response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.json()}"
        clone_id = update_response.json()["pending_update"]["id"]

        # Act: Admin rechaza el clone
        response = await client.put(
            f"/api/v1/golf-courses/admin/{clone_id}/reject-update", cookies=admin["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        # Original sin cambios
        assert data["original_golf_course"]["name"] == golf_course["name"]
        assert data["original_golf_course"]["approval_status"] == "APPROVED"
        assert data["original_golf_course"]["is_pending_update"] is False
        assert data["rejected_clone_id"] == clone_id

    @pytest.mark.asyncio
    async def test_non_admin_cannot_reject_update_returns_403(self, client: AsyncClient):
        """Usuario no-admin no puede rechazar updates."""
        # Arrange: Crear campo APPROVED y luego clone
        admin = await create_authenticated_user(
            client, "admin13@test.com", "AdminPass123!", "Admin", "Thirteen"
        )

        async def make_admin():
            from main import app as fastapi_app
            from src.config.dependencies import get_db_session

            db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
            async for session in db_session_override():
                try:
                    await session.execute(
                        text("UPDATE users SET is_admin = true WHERE email = :email"),
                        {"email": "admin13@test.com"},
                    )
                    await session.commit()
                    break
                finally:
                    await session.close()

        await make_admin()

        creator = await create_authenticated_user(
            client, "creator21@test.com", "P@ssw0rd123!", "Creator", "TwentyOne"
        )
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Creator crea clone
        update_data = {
            "name": "Clone Reject Attempt",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "tees": [
                {
                    "identifier": "White",
                    "tee_category": "CHAMPIONSHIP",
                    "tee_gender": "MALE",
                    "course_rating": 72.0,
                    "slope_rating": 130,
                    "par": 72,
                },
                {
                    "identifier": "Yellow",
                    "tee_category": "AMATEUR",
                    "tee_gender": "MALE",
                    "course_rating": 70.0,
                    "slope_rating": 125,
                    "par": 72,
                },
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        }

        update_response = await client.put(
            f"/api/v1/golf-courses/{golf_course['id']}",
            json=update_data,
            cookies=creator["cookies"],
        )
        clone_id = update_response.json()["pending_update"]["id"]

        # Act: Non-admin intenta rechazar
        other_user = await create_authenticated_user(
            client, "other6@test.com", "OtherPass123!", "Other", "Six"
        )

        response = await client.put(
            f"/api/v1/golf-courses/admin/{clone_id}/reject-update", cookies=other_user["cookies"]
        )

        # Assert
        assert response.status_code == 403
