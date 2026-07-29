"""
Tests E2E para Friend Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de amistad incluyendo autenticación, validaciones y persistencia.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies


class TestSendFriendRequest:
    """Tests para POST /api/v1/friends/requests"""

    @pytest.mark.asyncio
    async def test_send_friend_request_success(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_a@test.com", "P@ssw0rd123!", "Friend", "Aa"
        )
        b = await create_authenticated_user(
            client, "friend_b@test.com", "P@ssw0rd123!", "Friend", "Bb"
        )

        set_auth_cookies(client, a["cookies"])
        response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["requester_id"] == a["user"]["id"]
        assert data["addressee_id"] == b["user"]["id"]

    @pytest.mark.asyncio
    async def test_self_request_returns_400(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "friend_solo@test.com", "P@ssw0rd123!", "Solo", "User"
        )

        set_auth_cookies(client, user["cookies"])
        response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": user["user"]["id"]}
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_request_returns_409(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_c@test.com", "P@ssw0rd123!", "Friend", "Cc"
        )
        b = await create_authenticated_user(
            client, "friend_d@test.com", "P@ssw0rd123!", "Friend", "Dd"
        )

        set_auth_cookies(client, a["cookies"])
        await client.post("/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]})
        response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_resend_after_decline_succeeds(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_o@test.com", "P@ssw0rd123!", "Friend", "Oo"
        )
        b = await create_authenticated_user(
            client, "friend_p@test.com", "P@ssw0rd123!", "Friend", "Pp"
        )

        set_auth_cookies(client, a["cookies"])
        first_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )
        friendship_id = first_response.json()["id"]

        set_auth_cookies(client, b["cookies"])
        await client.post(
            f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "DECLINE"}
        )

        set_auth_cookies(client, a["cookies"])
        second_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )

        assert second_response.status_code == 201
        assert second_response.json()["status"] == "PENDING"


class TestRespondFriendRequest:
    """Tests para POST /api/v1/friends/requests/{id}/respond"""

    @pytest.mark.asyncio
    async def test_accept_success(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_e@test.com", "P@ssw0rd123!", "Friend", "Ee"
        )
        b = await create_authenticated_user(
            client, "friend_f@test.com", "P@ssw0rd123!", "Friend", "Ff"
        )

        set_auth_cookies(client, a["cookies"])
        send_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )
        friendship_id = send_response.json()["id"]

        set_auth_cookies(client, b["cookies"])
        response = await client.post(
            f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ACCEPTED"

    @pytest.mark.asyncio
    async def test_non_addressee_cannot_respond(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_g@test.com", "P@ssw0rd123!", "Friend", "Gg"
        )
        b = await create_authenticated_user(
            client, "friend_h@test.com", "P@ssw0rd123!", "Friend", "Hh"
        )

        set_auth_cookies(client, a["cookies"])
        send_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )
        friendship_id = send_response.json()["id"]

        # El propio requester intenta aceptar su propia solicitud
        response = await client.post(
            f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
        )

        assert response.status_code == 403


class TestRemoveFriend:
    """Tests para DELETE /api/v1/friends/{id}"""

    @pytest.mark.asyncio
    async def test_unfriend_success(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_i@test.com", "P@ssw0rd123!", "Friend", "Ii"
        )
        b = await create_authenticated_user(
            client, "friend_j@test.com", "P@ssw0rd123!", "Friend", "Jj"
        )

        set_auth_cookies(client, a["cookies"])
        send_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )
        friendship_id = send_response.json()["id"]

        set_auth_cookies(client, b["cookies"])
        await client.post(
            f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
        )

        response = await client.delete(f"/api/v1/friends/{friendship_id}")

        assert response.status_code == 204


class TestListFriends:
    """Tests para GET /api/v1/friends/me"""

    @pytest.mark.asyncio
    async def test_list_friends_returns_accepted_only(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_k@test.com", "P@ssw0rd123!", "Friend", "Kk"
        )
        b = await create_authenticated_user(
            client, "friend_l@test.com", "P@ssw0rd123!", "Friend", "Ll"
        )

        set_auth_cookies(client, a["cookies"])
        send_response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
        )
        friendship_id = send_response.json()["id"]

        set_auth_cookies(client, b["cookies"])
        await client.post(
            f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
        )

        response = await client.get("/api/v1/friends/me")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["friendships"][0]["status"] == "ACCEPTED"


class TestBlockUser:
    """Tests para POST /api/v1/friends/{user_id}/block"""

    @pytest.mark.asyncio
    async def test_block_prevents_future_requests(self, client: AsyncClient):
        a = await create_authenticated_user(
            client, "friend_m@test.com", "P@ssw0rd123!", "Friend", "Mm"
        )
        b = await create_authenticated_user(
            client, "friend_n@test.com", "P@ssw0rd123!", "Friend", "Nn"
        )

        set_auth_cookies(client, a["cookies"])
        block_response = await client.post(f"/api/v1/friends/{b['user']['id']}/block")
        assert block_response.status_code == 200
        assert block_response.json()["status"] == "BLOCKED"

        set_auth_cookies(client, b["cookies"])
        response = await client.post(
            "/api/v1/friends/requests", json={"addressee_id": a["user"]["id"]}
        )

        assert response.status_code == 403
