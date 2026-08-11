"""
Tests E2E del interruptor de publicacion de logros (BE #175).

PUT /api/v1/social/activity-sharing
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies


class TestSetActivitySharing:
    @pytest.mark.asyncio
    async def test_turning_it_off_returns_the_new_state(self, client: AsyncClient):
        """Given un jugador / When lo apaga / Then la respuesta lo confirma."""
        user = await create_authenticated_user(
            client, "sharing_off@test.com", "P@ssw0rd123!", "Share", "Off"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.put(
            "/api/v1/social/activity-sharing", json={"enabled": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["share_activity"] is False
        # Sin nada publicado todavia, no hay nada que retirar
        assert data["removed_events"] == 0

    @pytest.mark.asyncio
    async def test_turning_it_back_on_removes_nothing(self, client: AsyncClient):
        """Given un jugador que lo enciende / When lo enciende / Then no borra nada."""
        user = await create_authenticated_user(
            client, "sharing_on@test.com", "P@ssw0rd123!", "Share", "On"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.put(
            "/api/v1/social/activity-sharing", json={"enabled": True}
        )

        assert response.status_code == 200
        assert response.json() == {"share_activity": True, "removed_events": 0}

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client: AsyncClient):
        """Given nadie autenticado / When se llama / Then no se permite."""
        client.cookies.clear()

        response = await client.put(
            "/api/v1/social/activity-sharing", json={"enabled": False}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_a_body_without_the_switch(self, client: AsyncClient):
        """Given un cuerpo sin `enabled` / When se llama / Then se rechaza."""
        user = await create_authenticated_user(
            client, "sharing_bad@test.com", "P@ssw0rd123!", "Share", "Bad"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.put("/api/v1/social/activity-sharing", json={})

        assert response.status_code == 422
