"""
Tests E2E para Quick Match Endpoints.

Tests de integración que verifican el flujo completo de partidas rapidas
incluyendo autenticación, validaciones y persistencia.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_golf_course,
    set_auth_cookies,
)


async def _make_friends(client: AsyncClient, a: dict, b: dict) -> None:
    """Helper: crea una amistad ACCEPTED entre dos usuarios via la API."""
    set_auth_cookies(client, a["cookies"])
    send_response = await client.post(
        "/api/v1/friends/requests", json={"addressee_id": b["user"]["id"]}
    )
    assert send_response.status_code == 201, send_response.text
    friendship_id = send_response.json()["id"]

    set_auth_cookies(client, b["cookies"])
    respond_response = await client.post(
        f"/api/v1/friends/requests/{friendship_id}/respond", json={"action": "ACCEPT"}
    )
    assert respond_response.status_code == 200, respond_response.text


async def _create_approved_golf_course(client: AsyncClient, admin: dict, creator: dict) -> str:
    course = await create_golf_course(client, creator["cookies"])
    await approve_golf_course(client, admin["cookies"], course["id"])
    return course["id"]


class TestCreateQuickMatch:
    """Tests para POST /api/v1/quick-matches"""

    @pytest.mark.asyncio
    async def test_create_success(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin1@test.com", "P@ssw0rd123!", "Admin", "One"
        )
        creator = await create_authenticated_user(
            client, "qm_creator1@test.com", "P@ssw0rd123!", "Creator", "One"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"
        assert len(data["participants"]) == 1
        assert data["scorer_ids"] == []

    @pytest.mark.asyncio
    async def test_create_with_name_round_trips(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_name@test.com", "P@ssw0rd123!", "Admin", "Name"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_name@test.com", "P@ssw0rd123!", "Creator", "Name"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "name": "  Viernes con Rafa  ",
            },
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Viernes con Rafa"

        quick_match_id = response.json()["id"]
        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["name"] == "Viernes con Rafa"

    @pytest.mark.asyncio
    async def test_create_without_name_returns_null(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_noname@test.com", "P@ssw0rd123!", "Admin", "NoName"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_noname@test.com", "P@ssw0rd123!", "Creator", "NoName"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )

        assert response.status_code == 201
        assert response.json()["name"] is None

    @pytest.mark.asyncio
    async def test_create_with_name_over_max_length_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_long@test.com", "P@ssw0rd123!", "Admin", "Long"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_long@test.com", "P@ssw0rd123!", "Creator", "Long"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "name": "a" * 101,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_with_unapproved_course_returns_422(self, client: AsyncClient):
        creator = await create_authenticated_user(
            client, "qm_creator2@test.com", "P@ssw0rd123!", "Creator", "Two"
        )
        course = await create_golf_course(client, creator["cookies"])

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": course["id"], "match_format": "SINGLES"},
        )

        assert response.status_code == 422


class TestQuickMatchFullFlow:
    """Flujo completo: crear, añadir amigo, iniciar, registrar scores, ver detalle."""

    @pytest.mark.asyncio
    async def test_full_flow_singles(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin2@test.com", "P@ssw0rd123!", "Admin", "Two")
        creator = await create_authenticated_user(
            client, "qm_creator3@test.com", "P@ssw0rd123!", "Creator", "Three"
        )
        friend = await create_authenticated_user(
            client, "qm_friend3@test.com", "P@ssw0rd123!", "Friend", "Three"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)
        await _make_friends(client, creator, friend)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]

        add_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants",
            json={"friend_user_id": friend["user"]["id"]},
        )
        assert add_response.status_code == 201
        assert len(add_response.json()["participants"]) == 2  # noqa: PLR2004

        start_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [creator["user"]["id"], friend["user"]["id"]]},
        )
        assert start_response.status_code == 200, start_response.text
        assert start_response.json()["status"] == "IN_PROGRESS"

        score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/1/score", json={"score": 4}
        )
        assert score_response.status_code == 200
        assert score_response.json()["score"] == 4  # noqa: PLR2004

        set_auth_cookies(client, friend["cookies"])
        friend_score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/1/score", json={"score": 5}
        )
        assert friend_score_response.status_code == 200

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert len(detail["hole_scores"]) == 2  # noqa: PLR2004
        assert detail["standing"]["holes_played"] == 1

        set_auth_cookies(client, creator["cookies"])
        complete_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/complete"
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_add_non_friend_returns_403(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin3@test.com", "P@ssw0rd123!", "Admin", "Three")
        creator = await create_authenticated_user(
            client, "qm_creator4@test.com", "P@ssw0rd123!", "Creator", "Four"
        )
        stranger = await create_authenticated_user(
            client, "qm_stranger4@test.com", "P@ssw0rd123!", "Stranger", "Four"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]

        response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants",
            json={"friend_user_id": stranger["user"]["id"]},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_my_quick_matches(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin4@test.com", "P@ssw0rd123!", "Admin", "Four")
        creator = await create_authenticated_user(
            client, "qm_creator5@test.com", "P@ssw0rd123!", "Creator", "Five"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )

        response = await client.get("/api/v1/quick-matches/me")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1


class TestQuickMatchGuestsAndScoringAssignment:
    """Flujo con jugador invitado (sin cuenta) y anotacion por delegacion."""

    @pytest.mark.asyncio
    async def test_add_guest_and_proxy_score(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin5@test.com", "P@ssw0rd123!", "Admin", "Five")
        creator = await create_authenticated_user(
            client, "qm_creator6@test.com", "P@ssw0rd123!", "Creator", "Six"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]

        guest_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants/guest",
            json={"first_name": "Jane", "last_name": "Doe", "handicap": 18.4},
        )
        assert guest_response.status_code == 201, guest_response.text
        guest_dto = next(p for p in guest_response.json()["participants"] if p["is_guest"])
        assert guest_dto["name"] == "Jane Doe"
        assert guest_dto["handicap"] == 18.4  # noqa: PLR2004
        guest_participant_id = guest_dto["participant_id"]

        # Solo el creador anota (1 anotador): debe cubrir tambien al invitado.
        start_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [creator["user"]["id"]]},
        )
        assert start_response.status_code == 200, start_response.text

        own_score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/1/score", json={"score": 4}
        )
        assert own_score_response.status_code == 200

        proxy_score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{guest_participant_id}"
            "/holes/1/score",
            json={"score": 6},
        )
        assert proxy_score_response.status_code == 200, proxy_score_response.text
        proxy_data = proxy_score_response.json()
        assert proxy_data["participant_id"] == guest_participant_id
        assert proxy_data["recorded_by_participant_id"] == creator["user"]["id"]

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert len(detail["hole_scores"]) == 2  # noqa: PLR2004
        assert len(detail["scoring_assignments"]) == 1
        assert set(detail["scoring_assignments"][0]["covered_participant_ids"]) == {
            creator["user"]["id"],
            guest_participant_id,
        }

    @pytest.mark.asyncio
    async def test_non_scorer_cannot_self_submit(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin6@test.com", "P@ssw0rd123!", "Admin", "Six")
        creator = await create_authenticated_user(
            client, "qm_creator7@test.com", "P@ssw0rd123!", "Creator", "Seven"
        )
        friend = await create_authenticated_user(
            client, "qm_friend7@test.com", "P@ssw0rd123!", "Friend", "Seven"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)
        await _make_friends(client, creator, friend)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]
        await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants",
            json={"friend_user_id": friend["user"]["id"]},
        )
        # Solo el creador anota; `friend` es participante pero no anotador.
        await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [creator["user"]["id"]]},
        )

        set_auth_cookies(client, friend["cookies"])
        response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/1/score", json={"score": 5}
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_start_without_creator_as_scorer_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(client, "qm_admin7@test.com", "P@ssw0rd123!", "Admin", "Seven")
        creator = await create_authenticated_user(
            client, "qm_creator8@test.com", "P@ssw0rd123!", "Creator", "Eight"
        )
        friend = await create_authenticated_user(
            client, "qm_friend8@test.com", "P@ssw0rd123!", "Friend", "Eight"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)
        await _make_friends(client, creator, friend)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]
        await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants",
            json={"friend_user_id": friend["user"]["id"]},
        )

        response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [friend["user"]["id"]]},
        )

        assert response.status_code == 422
