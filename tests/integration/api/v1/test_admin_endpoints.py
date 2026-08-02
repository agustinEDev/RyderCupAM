"""Tests de integración para /api/v1/admin/* (panel de administración)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import (
    create_authenticated_user,
    create_golf_course,
    set_auth_cookies,
)


async def _make_admin(email: str) -> None:
    from main import app as fastapi_app
    from src.config.dependencies import get_db_session

    db_session_override = fastapi_app.dependency_overrides[get_db_session]
    async for session in db_session_override():
        try:
            await session.execute(
                text("UPDATE users SET is_admin = true WHERE email = :email"),
                {"email": email},
            )
            await session.commit()
            break
        finally:
            await session.close()


class TestAdminStats:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_get_stats_returns_403(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "notadmin_stats@test.com", "P@ssw0rd123!", "Not", "Admin"
        )
        response = await client.get("/api/v1/admin/stats", cookies=user["cookies"])
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_gets_stats(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_stats@test.com", "AdminPass123!", "Admin", "Stats"
        )
        await _make_admin("admin_stats@test.com")

        response = await client.get("/api/v1/admin/stats", cookies=admin["cookies"])
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert data["total_users"] >= 1
        assert "total_competitions" in data
        assert "total_quick_matches" in data
        assert "total_golf_courses_approved" in data
        assert "total_golf_courses_pending" in data


class TestAdminListUsers:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_users_returns_403(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "notadmin_list@test.com", "P@ssw0rd123!", "Not", "Admin"
        )
        response = await client.get("/api/v1/admin/users", cookies=user["cookies"])
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_lists_and_searches_users(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_list@test.com", "AdminPass123!", "Admin", "List"
        )
        await _make_admin("admin_list@test.com")
        await create_authenticated_user(
            client, "findable_target@test.com", "P@ssw0rd123!", "Findable", "Target"
        )

        response = await client.get(
            "/api/v1/admin/users", params={"search": "findable_target"}, cookies=admin["cookies"]
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["users"][0]["email"] == "findable_target@test.com"


class TestAdminUpdateUser:
    @pytest.mark.asyncio
    async def test_admin_updates_user(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_update@test.com", "AdminPass123!", "Admin", "Update"
        )
        await _make_admin("admin_update@test.com")
        target = await create_authenticated_user(
            client, "target_update@test.com", "P@ssw0rd123!", "Target", "User"
        )

        response = await client.put(
            f"/api/v1/admin/users/{target['user']['id']}",
            json={"first_name": "Renamed", "handicap": 15.3},
            cookies=admin["cookies"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Renamed"
        assert data["handicap"] == 15.3

    @pytest.mark.asyncio
    async def test_admin_update_duplicate_email_returns_409(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_dup@test.com", "AdminPass123!", "Admin", "Dup"
        )
        await _make_admin("admin_dup@test.com")
        await create_authenticated_user(
            client, "already_taken@test.com", "P@ssw0rd123!", "Taken", "User"
        )
        target = await create_authenticated_user(
            client, "target_dup@test.com", "P@ssw0rd123!", "Target", "User"
        )

        response = await client.put(
            f"/api/v1/admin/users/{target['user']['id']}",
            json={"email": "already_taken@test.com"},
            cookies=admin["cookies"],
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_non_admin_cannot_update_user_returns_403(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "notadmin_update@test.com", "P@ssw0rd123!", "Not", "Admin"
        )
        target = await create_authenticated_user(
            client, "target_notadmin@test.com", "P@ssw0rd123!", "Target", "User"
        )
        response = await client.put(
            f"/api/v1/admin/users/{target['user']['id']}",
            json={"first_name": "Hacked"},
            cookies=user["cookies"],
        )
        assert response.status_code == 403


class TestAdminSetUserActive:
    @pytest.mark.asyncio
    async def test_admin_deactivates_and_blocks_login(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_deact@test.com", "AdminPass123!", "Admin", "Deact"
        )
        await _make_admin("admin_deact@test.com")
        target = await create_authenticated_user(
            client, "target_deact@test.com", "P@ssw0rd123!", "Target", "User"
        )

        response = await client.put(
            f"/api/v1/admin/users/{target['user']['id']}/active",
            json={"is_active": False},
            cookies=admin["cookies"],
        )
        assert response.status_code == 204

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "target_deact@test.com", "password": "P@ssw0rd123!"},
            headers={"X-Test-Client-ID": f"login-{uuid.uuid4()}"},
        )
        assert login_response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_reactivates_user(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_react@test.com", "AdminPass123!", "Admin", "React"
        )
        await _make_admin("admin_react@test.com")
        target = await create_authenticated_user(
            client, "target_react@test.com", "P@ssw0rd123!", "Target", "User"
        )

        await client.put(
            f"/api/v1/admin/users/{target['user']['id']}/active",
            json={"is_active": False},
            cookies=admin["cookies"],
        )
        response = await client.put(
            f"/api/v1/admin/users/{target['user']['id']}/active",
            json={"is_active": True},
            cookies=admin["cookies"],
        )
        assert response.status_code == 204

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "target_react@test.com", "password": "P@ssw0rd123!"},
            headers={"X-Test-Client-ID": f"login-{uuid.uuid4()}"},
        )
        assert login_response.status_code == 200


class TestAdminDeleteUser:
    @pytest.mark.asyncio
    async def test_admin_deletes_clean_user(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_delete@test.com", "AdminPass123!", "Admin", "Delete"
        )
        await _make_admin("admin_delete@test.com")
        target = await create_authenticated_user(
            client, "target_delete@test.com", "P@ssw0rd123!", "Target", "User"
        )

        response = await client.delete(
            f"/api/v1/admin/users/{target['user']['id']}", cookies=admin["cookies"]
        )
        assert response.status_code == 204

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "target_delete@test.com", "password": "P@ssw0rd123!"},
            headers={"X-Test-Client-ID": f"login-{uuid.uuid4()}"},
        )
        assert login_response.status_code == 401

    @pytest.mark.asyncio
    async def test_non_admin_cannot_delete_user_returns_403(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "notadmin_delete@test.com", "P@ssw0rd123!", "Not", "Admin"
        )
        target = await create_authenticated_user(
            client, "target_notadmin_delete@test.com", "P@ssw0rd123!", "Target", "User"
        )
        response = await client.delete(
            f"/api/v1/admin/users/{target['user']['id']}", cookies=user["cookies"]
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_delete_blocked_when_user_has_activity(self, client: AsyncClient):
        """Bloquea (409) el borrado definitivo si el usuario tiene actividad,
        para no romper la restricción de BD (golf_courses.creator_id sin
        ON DELETE) ni el dato de otros (competitions/quick_matches CASCADE).
        La cuenta debe seguir existiendo tras el intento fallido."""
        admin = await create_authenticated_user(
            client, "admin_delete_blocked@test.com", "AdminPass123!", "Admin", "Blocked"
        )
        await _make_admin("admin_delete_blocked@test.com")
        target = await create_authenticated_user(
            client, "target_delete_blocked@test.com", "P@ssw0rd123!", "Target", "User"
        )

        await create_golf_course(client, target["cookies"])

        set_auth_cookies(client, admin["cookies"])
        response = await client.delete(f"/api/v1/admin/users/{target['user']['id']}")
        assert response.status_code == 409
        assert "golf course" in response.json()["detail"]

        list_response = await client.get(
            "/api/v1/admin/users", params={"search": "target_delete_blocked"}
        )
        assert list_response.status_code == 200
        assert list_response.json()["total_count"] == 1

    @pytest.mark.asyncio
    async def test_admin_cannot_delete_own_account(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_self_delete@test.com", "AdminPass123!", "Admin", "Self"
        )
        await _make_admin("admin_self_delete@test.com")

        response = await client.delete(
            f"/api/v1/admin/users/{admin['user']['id']}", cookies=admin["cookies"]
        )
        assert response.status_code == 400


class TestAdminSelfDeactivationGuard:
    @pytest.mark.asyncio
    async def test_admin_cannot_deactivate_own_account(self, client: AsyncClient):
        admin = await create_authenticated_user(
            client, "admin_self_deact@test.com", "AdminPass123!", "Admin", "SelfDeact"
        )
        await _make_admin("admin_self_deact@test.com")

        response = await client.put(
            f"/api/v1/admin/users/{admin['user']['id']}/active",
            json={"is_active": False},
            cookies=admin["cookies"],
        )
        assert response.status_code == 400
