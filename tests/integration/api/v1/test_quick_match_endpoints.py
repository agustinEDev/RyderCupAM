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

    @pytest.mark.asyncio
    async def test_create_without_any_format_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_noformat@test.com", "P@ssw0rd123!", "Admin", "NoFormat"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_noformat@test.com", "P@ssw0rd123!", "Creator", "NoFormat"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches", json={"golf_course_id": golf_course_id}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_with_both_formats_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_bothformat@test.com", "P@ssw0rd123!", "Admin", "BothFormat"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_bothformat@test.com", "P@ssw0rd123!", "Creator", "BothFormat"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "scoring_format": "MEDAL",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_free_play_success(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_freeplay@test.com", "P@ssw0rd123!", "Admin", "FreePlay"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_freeplay@test.com", "P@ssw0rd123!", "Creator", "FreePlay"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "scoring_format": "STABLEFORD"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["match_format"] is None
        assert data["scoring_format"] == "STABLEFORD"
        assert data["participants"][0]["team"] is None


class TestQuickMatchTeeAndAllowance:
    """Playing Handicap: tee por participante + allowance % personalizable por el creador."""

    @pytest.mark.asyncio
    async def test_default_effective_allowance_by_format(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_allowance@test.com", "P@ssw0rd123!", "Admin", "Allowance"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_allowance@test.com", "P@ssw0rd123!", "Creator", "Allowance"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "FOURBALL"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["allowance_percentage"] is None
        assert data["effective_allowance"] == 90  # WHS default para FOURBALL

    @pytest.mark.asyncio
    async def test_custom_allowance_overrides_default(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_customallow@test.com", "P@ssw0rd123!", "Admin", "CustomAllow"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_customallow@test.com", "P@ssw0rd123!", "Creator", "CustomAllow"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "allowance_percentage": 80,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["allowance_percentage"] == 80
        assert data["effective_allowance"] == 80

    @pytest.mark.asyncio
    async def test_allowance_not_multiple_of_five_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_badallow@test.com", "P@ssw0rd123!", "Admin", "BadAllow"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_badallow@test.com", "P@ssw0rd123!", "Creator", "BadAllow"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "allowance_percentage": 77,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_creator_and_friend_tee_selection_round_trips(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_tee@test.com", "P@ssw0rd123!", "Admin", "Tee"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_tee@test.com", "P@ssw0rd123!", "Creator", "Tee"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_tee@test.com", "P@ssw0rd123!", "Friend", "Tee"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)
        await _make_friends(client, creator, friend)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                "creator_tee_color": "YELLOW",
                "creator_tee_gender": "MALE",
            },
        )
        assert create_response.status_code == 201
        quick_match_id = create_response.json()["id"]
        creator_dto = create_response.json()["participants"][0]
        assert creator_dto["tee_color"] == "YELLOW"
        assert creator_dto["tee_gender"] == "MALE"

        add_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/participants",
            json={
                "friend_user_id": friend["user"]["id"],
                "tee_color": "WHITE",
                "tee_gender": "MALE",
            },
        )
        assert add_response.status_code == 201
        friend_dto = next(
            p for p in add_response.json()["participants"] if p["user_id"] == friend["user"]["id"]
        )
        assert friend_dto["tee_color"] == "WHITE"
        assert friend_dto["tee_gender"] == "MALE"

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        detail_creator_dto = next(
            p
            for p in detail_response.json()["participants"]
            if p["user_id"] == creator["user"]["id"]
        )
        assert detail_creator_dto["tee_color"] == "YELLOW"

    @pytest.mark.asyncio
    async def test_create_with_tee_not_on_course_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_badtee@test.com", "P@ssw0rd123!", "Admin", "BadTee"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_badtee@test.com", "P@ssw0rd123!", "Creator", "BadTee"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches",
            json={
                "golf_course_id": golf_course_id,
                "match_format": "SINGLES",
                # the test golf course fixture only has CHAMPIONSHIP/MALE and AMATEUR/MALE tees
                "creator_tee_color": "RED",
                "creator_tee_gender": "FEMALE",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_friend_with_tee_not_on_course_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_badtee2@test.com", "P@ssw0rd123!", "Admin", "BadTeeFriend"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_badtee2@test.com", "P@ssw0rd123!", "Creator", "BadTeeFriend"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_badtee2@test.com", "P@ssw0rd123!", "Friend", "BadTeeFriend"
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
            json={
                "friend_user_id": friend["user"]["id"],
                "tee_color": "RED",
                "tee_gender": "FEMALE",
            },
        )

        assert add_response.status_code == 422


class TestQuickMatchFreePlayFlow:
    """Partido libre: 1 a 4 jugadores, sin equipos, se puede jugar en solitario."""

    @pytest.mark.asyncio
    async def test_solo_free_play_start_and_score(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_solo@test.com", "P@ssw0rd123!", "Admin", "Solo"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_solo@test.com", "P@ssw0rd123!", "Creator", "Solo"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "scoring_format": "MEDAL"},
        )
        assert create_response.status_code == 201
        quick_match_id = create_response.json()["id"]
        creator_participant_id = create_response.json()["participants"][0]["participant_id"]

        start_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [creator_participant_id]},
        )
        assert start_response.status_code == 200, start_response.text
        assert start_response.json()["status"] == "IN_PROGRESS"

        score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/1/score", json={"score": 4}
        )
        assert score_response.status_code == 200, score_response.text

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["standing"] is None
        assert len(detail["hole_scores"]) == 1


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


class TestQuickMatchSetParticipantHandicap:
    """Tests para PATCH /api/v1/quick-matches/{id}/participants/{participant_id}/handicap"""

    @pytest.mark.asyncio
    async def test_creator_overrides_registered_participant_without_profile_handicap(
        self, client: AsyncClient
    ):
        admin = await create_admin_user(
            client, "qm_admin_hc1@test.com", "P@ssw0rd123!", "Admin", "HcOne"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc1@test.com", "P@ssw0rd123!", "Creator", "HcOne"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_hc1@test.com", "P@ssw0rd123!", "Friend", "HcOne"
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
        friend_dto = next(
            p for p in add_response.json()["participants"] if p["user_id"] == friend["user"]["id"]
        )
        assert friend_dto["handicap"] is None

        response = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{friend_dto['participant_id']}"
            "/handicap",
            json={"handicap": 16.4},
        )

        assert response.status_code == 200, response.text
        updated_dto = next(
            p for p in response.json()["participants"] if p["participant_id"] == friend_dto["participant_id"]
        )
        assert updated_dto["handicap"] == 16.4

        # Re-fetch on a fresh request/DB session — the PATCH response alone reflects
        # the in-memory entity and doesn't prove the write actually reached Postgres.
        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        persisted_dto = next(
            p
            for p in detail_response.json()["participants"]
            if p["participant_id"] == friend_dto["participant_id"]
        )
        assert persisted_dto["handicap"] == 16.4

    @pytest.mark.asyncio
    async def test_editing_two_participants_handicaps_both_persist(self, client: AsyncClient):
        """
        Regression test: QuickMatchParticipant.__eq__ only compares participant_id
        (by domain design), so SQLAlchemy's default dirty-check on the `participants`
        JSONB column — which compares old vs new Python list via `==` — couldn't see
        a same-length list where only one entry's handicap changed, and silently
        skipped writing it. Editing a second participant would then persist only
        that one, discarding the first one's already-"saved" (but never actually
        written) override. Fixed by force-flagging the column as modified in
        SQLAlchemyQuickMatchRepository.update().
        """
        admin = await create_admin_user(
            client, "qm_admin_hc6@test.com", "P@ssw0rd123!", "Admin", "HcSix"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc6@test.com", "P@ssw0rd123!", "Creator", "HcSix"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_hc6@test.com", "P@ssw0rd123!", "Friend", "HcSix"
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
        friend_participant_id = next(
            p["participant_id"]
            for p in add_response.json()["participants"]
            if p["user_id"] == friend["user"]["id"]
        )
        creator_participant_id = creator["user"]["id"]

        first_patch = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{creator_participant_id}"
            "/handicap",
            json={"handicap": 15.0},
        )
        assert first_patch.status_code == 200, first_patch.text

        second_patch = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{friend_participant_id}"
            "/handicap",
            json={"handicap": 20.0},
        )
        assert second_patch.status_code == 200, second_patch.text

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        participants_by_id = {
            p["participant_id"]: p["handicap"] for p in detail_response.json()["participants"]
        }
        assert participants_by_id[creator_participant_id] == 15.0
        assert participants_by_id[friend_participant_id] == 20.0

    @pytest.mark.asyncio
    async def test_creator_edits_guest_handicap(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_hc2@test.com", "P@ssw0rd123!", "Admin", "HcTwo"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc2@test.com", "P@ssw0rd123!", "Creator", "HcTwo"
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
        guest_participant_id = next(
            p for p in guest_response.json()["participants"] if p["is_guest"]
        )["participant_id"]

        response = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{guest_participant_id}"
            "/handicap",
            json={"handicap": 20.1},
        )

        assert response.status_code == 200, response.text
        updated_dto = next(
            p for p in response.json()["participants"] if p["participant_id"] == guest_participant_id
        )
        assert updated_dto["handicap"] == 20.1

        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        persisted_dto = next(
            p
            for p in detail_response.json()["participants"]
            if p["participant_id"] == guest_participant_id
        )
        assert persisted_dto["handicap"] == 20.1

    @pytest.mark.asyncio
    async def test_non_creator_cannot_edit_handicap_returns_403(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_hc3@test.com", "P@ssw0rd123!", "Admin", "HcThree"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc3@test.com", "P@ssw0rd123!", "Creator", "HcThree"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_hc3@test.com", "P@ssw0rd123!", "Friend", "HcThree"
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
        friend_participant_id = next(
            p["participant_id"]
            for p in add_response.json()["participants"]
            if p["user_id"] == friend["user"]["id"]
        )

        set_auth_cookies(client, friend["cookies"])
        response = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{friend_participant_id}"
            "/handicap",
            json={"handicap": 10.0},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_edit_handicap_after_start_returns_409(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_hc4@test.com", "P@ssw0rd123!", "Admin", "HcFour"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc4@test.com", "P@ssw0rd123!", "Creator", "HcFour"
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
            json={"first_name": "Jane", "last_name": "Doe"},
        )
        guest_participant_id = next(
            p for p in guest_response.json()["participants"] if p["is_guest"]
        )["participant_id"]

        await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/start",
            json={"scorer_ids": [creator["user"]["id"]]},
        )

        response = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{guest_participant_id}"
            "/handicap",
            json={"handicap": 10.0},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_edit_handicap_out_of_range_returns_422(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "qm_admin_hc5@test.com", "P@ssw0rd123!", "Admin", "HcFive"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hc5@test.com", "P@ssw0rd123!", "Creator", "HcFive"
        )
        golf_course_id = await _create_approved_golf_course(client, admin, creator)

        set_auth_cookies(client, creator["cookies"])
        create_response = await client.post(
            "/api/v1/quick-matches",
            json={"golf_course_id": golf_course_id, "match_format": "SINGLES"},
        )
        quick_match_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/quick-matches/{quick_match_id}/participants/{creator['user']['id']}"
            "/handicap",
            json={"handicap": 99},
        )

        assert response.status_code == 422


class TestQuickMatchHideFromHistory:
    """Tests para POST/DELETE /api/v1/quick-matches/{id}/hide (RyderCupAm#127)."""

    async def _create_match_with_two_participants(
        self, client: AsyncClient
    ) -> tuple[dict, dict, dict, str]:
        admin = await create_admin_user(
            client, "qm_admin_hide1@test.com", "P@ssw0rd123!", "Admin", "HideOne"
        )
        creator = await create_authenticated_user(
            client, "qm_creator_hide1@test.com", "P@ssw0rd123!", "Creator", "HideOne"
        )
        friend = await create_authenticated_user(
            client, "qm_friend_hide1@test.com", "P@ssw0rd123!", "Friend", "HideOne"
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

        return admin, creator, friend, quick_match_id

    @pytest.mark.asyncio
    async def test_hide_removes_it_from_my_list_but_not_from_the_other_participant(
        self, client: AsyncClient
    ):
        _admin, creator, friend, quick_match_id = await self._create_match_with_two_participants(
            client
        )

        set_auth_cookies(client, creator["cookies"])
        hide_response = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")
        assert hide_response.status_code == 200, hide_response.text

        my_matches = await client.get("/api/v1/quick-matches/me")
        assert quick_match_id not in [m["id"] for m in my_matches.json()["quick_matches"]]

        # El otro participante, que no la ha ocultado, la sigue viendo.
        set_auth_cookies(client, friend["cookies"])
        friend_matches = await client.get("/api/v1/quick-matches/me")
        assert quick_match_id in [m["id"] for m in friend_matches.json()["quick_matches"]]

        # Tampoco se ha borrado ni afectado el registro en si.
        detail_response = await client.get(f"/api/v1/quick-matches/{quick_match_id}")
        assert detail_response.status_code == 200
        assert len(detail_response.json()["participants"]) == 2

    @pytest.mark.asyncio
    async def test_non_creator_participant_can_hide_it_too(self, client: AsyncClient):
        _admin, _creator, friend, quick_match_id = await self._create_match_with_two_participants(
            client
        )

        set_auth_cookies(client, friend["cookies"])
        response = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")

        assert response.status_code == 200, response.text
        my_matches = await client.get("/api/v1/quick-matches/me")
        assert quick_match_id not in [m["id"] for m in my_matches.json()["quick_matches"]]

    @pytest.mark.asyncio
    async def test_hide_is_idempotent(self, client: AsyncClient):
        _admin, creator, _friend, quick_match_id = await self._create_match_with_two_participants(
            client
        )

        set_auth_cookies(client, creator["cookies"])
        first = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")
        second = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")

        assert first.status_code == 200
        assert second.status_code == 200

    @pytest.mark.asyncio
    async def test_unhide_brings_it_back_to_my_list(self, client: AsyncClient):
        _admin, creator, _friend, quick_match_id = await self._create_match_with_two_participants(
            client
        )
        set_auth_cookies(client, creator["cookies"])
        await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")

        unhide_response = await client.delete(f"/api/v1/quick-matches/{quick_match_id}/hide")
        assert unhide_response.status_code == 200, unhide_response.text

        my_matches = await client.get("/api/v1/quick-matches/me")
        assert quick_match_id in [m["id"] for m in my_matches.json()["quick_matches"]]

    @pytest.mark.asyncio
    async def test_hide_a_non_participant_match_returns_404(self, client: AsyncClient):
        _admin, _creator, _friend, quick_match_id = (
            await self._create_match_with_two_participants(client)
        )
        outsider = await create_authenticated_user(
            client, "qm_outsider_hide1@test.com", "P@ssw0rd123!", "Outsider", "HideOne"
        )

        set_auth_cookies(client, outsider["cookies"])
        response = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_hide_nonexistent_match_returns_404(self, client: AsyncClient):
        creator = await create_authenticated_user(
            client, "qm_creator_hide2@test.com", "P@ssw0rd123!", "Creator", "HideTwo"
        )

        set_auth_cookies(client, creator["cookies"])
        response = await client.post(
            "/api/v1/quick-matches/00000000-0000-0000-0000-000000000000/hide"
        )

        assert response.status_code == 404
