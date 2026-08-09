"""
Tests E2E de las estadísticas e historial del jugador (BE #128).

Cubren los tres endpoints de un tirón (`/me/stats`, `/me/stats/golf-courses/{id}`
y `/me/matches`) sobre una partida rápida jugada de verdad por la API: crear el
campo, crear la partida, anotar los 18 hoyos y terminarla. Es la única forma de
comprobar que la agregación entre módulos funciona con las unidades de trabajo
reales y no solo con las de memoria.
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

# El campo por defecto del helper son 18 hoyos de par 4
COURSE_PAR = 72
HOLES = range(1, 19)


async def _approved_golf_course(client: AsyncClient, admin: dict, creator: dict) -> str:
    course = await create_golf_course(client, creator["cookies"])
    await approve_golf_course(client, admin["cookies"], course["id"])
    return course["id"]


async def _played_medal_match(
    client: AsyncClient, player: dict, golf_course_id: str, strokes_per_hole: int = 5
) -> str:
    """Una partida libre MEDAL terminada con la vuelta entera anotada."""
    set_auth_cookies(client, player["cookies"])
    create_response = await client.post(
        "/api/v1/quick-matches",
        json={"golf_course_id": golf_course_id, "scoring_format": "MEDAL"},
    )
    assert create_response.status_code == 201, create_response.text
    quick_match_id = create_response.json()["id"]
    participant_id = create_response.json()["participants"][0]["participant_id"]

    start_response = await client.post(
        f"/api/v1/quick-matches/{quick_match_id}/start",
        json={"scorer_ids": [participant_id]},
    )
    assert start_response.status_code == 200, start_response.text

    for hole_number in HOLES:
        score_response = await client.post(
            f"/api/v1/quick-matches/{quick_match_id}/holes/{hole_number}/score",
            json={"score": strokes_per_hole},
        )
        assert score_response.status_code == 200, score_response.text

    complete_response = await client.post(f"/api/v1/quick-matches/{quick_match_id}/complete")
    assert complete_response.status_code == 200, complete_response.text
    return quick_match_id


class TestEmptyAccount:
    """Una cuenta nueva es un caso normal del panel, no un error."""

    @pytest.mark.asyncio
    async def test_stats_are_zero_and_null_not_a_404(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "stats_empty@test.com", "P@ssw0rd123!", "Empty", "Account"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.get("/api/v1/users/me/stats")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["rounds_played"] == 0
        assert body["tournaments_total"] == 0
        assert body["scoring_avg"] is None
        assert body["handicap_trend"] is None

    @pytest.mark.asyncio
    async def test_feed_is_an_empty_list(self, client: AsyncClient):
        user = await create_authenticated_user(
            client, "feed_empty@test.com", "P@ssw0rd123!", "Empty", "Feed"
        )
        set_auth_cookies(client, user["cookies"])

        response = await client.get("/api/v1/users/me/matches")

        assert response.status_code == 200, response.text
        assert response.json()["matches"] == []


class TestAuthentication:
    """Son datos personales: sin sesión no se ven."""

    @pytest.mark.asyncio
    async def test_stats_require_a_session(self, client: AsyncClient):
        client.cookies.clear()

        response = await client.get("/api/v1/users/me/stats")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_requires_a_session(self, client: AsyncClient):
        client.cookies.clear()

        response = await client.get("/api/v1/users/me/matches")

        assert response.status_code == 401


class TestPlayedQuickMatch:
    """Una partida jugada de verdad, vista desde los tres endpoints."""

    @pytest.mark.asyncio
    async def test_stats_count_the_round_and_average_the_net_score(self, client: AsyncClient):
        """
        Jugador sin hándicap en par 72, 5 golpes por hoyo: 90 brutos, +18. La
        media es el neto respecto al par, no los golpes brutos.
        """
        admin = await create_admin_user(
            client, "stats_admin1@test.com", "P@ssw0rd123!", "Admin", "Stats"
        )
        player = await create_authenticated_user(
            client, "stats_player1@test.com", "P@ssw0rd123!", "Played", "Round"
        )
        golf_course_id = await _approved_golf_course(client, admin, player)
        await _played_medal_match(client, player, golf_course_id)

        set_auth_cookies(client, player["cookies"])
        response = await client.get("/api/v1/users/me/stats")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["rounds_played"] == 1
        assert body["scoring_avg"] == 18.0

    @pytest.mark.asyncio
    async def test_feed_returns_the_match_with_its_course_and_score(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "stats_admin2@test.com", "P@ssw0rd123!", "Admin", "Feed"
        )
        player = await create_authenticated_user(
            client, "stats_player2@test.com", "P@ssw0rd123!", "Feed", "Player"
        )
        golf_course_id = await _approved_golf_course(client, admin, player)
        quick_match_id = await _played_medal_match(client, player, golf_course_id)

        set_auth_cookies(client, player["cookies"])
        response = await client.get("/api/v1/users/me/matches")

        assert response.status_code == 200, response.text
        matches = response.json()["matches"]
        assert len(matches) == 1
        entry = matches[0]
        assert entry["id"] == quick_match_id
        assert entry["golf_course_id"] == golf_course_id
        assert entry["golf_course_name"] is not None
        assert entry["scoring_format"] == "MEDAL"
        assert entry["score"] == "+18"
        # Un partido libre no se juega contra un rival ni pertenece a un torneo
        assert entry["match_format"] is None
        assert entry["result"] is None
        assert entry["tournament_name"] is None

    @pytest.mark.asyncio
    async def test_per_course_breakdown_counts_only_that_course(self, client: AsyncClient):
        """
        La partida se jugó en un campo: aparece en el desglose de ese campo y no
        en el de otro.
        """
        admin = await create_admin_user(
            client, "stats_admin3@test.com", "P@ssw0rd123!", "Admin", "Course"
        )
        player = await create_authenticated_user(
            client, "stats_player3@test.com", "P@ssw0rd123!", "Course", "Player"
        )
        played_course_id = await _approved_golf_course(client, admin, player)
        other_course_id = await _approved_golf_course(client, admin, player)
        await _played_medal_match(client, player, played_course_id)

        set_auth_cookies(client, player["cookies"])
        played = await client.get(f"/api/v1/users/me/stats/golf-courses/{played_course_id}")
        other = await client.get(f"/api/v1/users/me/stats/golf-courses/{other_course_id}")

        assert played.status_code == 200, played.text
        assert played.json()["rounds_played"] == 1
        assert played.json()["scoring_avg"] == 18.0
        assert other.status_code == 200, other.text
        assert other.json()["rounds_played"] == 0
        assert other.json()["scoring_avg"] is None

    @pytest.mark.asyncio
    async def test_limit_caps_the_feed(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "stats_admin4@test.com", "P@ssw0rd123!", "Admin", "Limit"
        )
        player = await create_authenticated_user(
            client, "stats_player4@test.com", "P@ssw0rd123!", "Limit", "Player"
        )
        golf_course_id = await _approved_golf_course(client, admin, player)
        await _played_medal_match(client, player, golf_course_id)
        await _played_medal_match(client, player, golf_course_id)

        set_auth_cookies(client, player["cookies"])
        response = await client.get("/api/v1/users/me/matches?limit=1")

        assert response.status_code == 200, response.text
        assert len(response.json()["matches"]) == 1


class TestHiddenMatches:
    """Regla de #127: ocultar una partida solo la retira para quien la oculta."""

    @pytest.mark.asyncio
    async def test_a_hidden_match_leaves_both_the_stats_and_the_feed(self, client: AsyncClient):
        admin = await create_admin_user(
            client, "stats_admin5@test.com", "P@ssw0rd123!", "Admin", "Hidden"
        )
        player = await create_authenticated_user(
            client, "stats_player5@test.com", "P@ssw0rd123!", "Hidden", "Player"
        )
        golf_course_id = await _approved_golf_course(client, admin, player)
        quick_match_id = await _played_medal_match(client, player, golf_course_id)

        set_auth_cookies(client, player["cookies"])
        hide_response = await client.post(f"/api/v1/quick-matches/{quick_match_id}/hide")
        assert hide_response.status_code == 200, hide_response.text

        stats = await client.get("/api/v1/users/me/stats")
        feed = await client.get("/api/v1/users/me/matches")

        assert stats.json()["rounds_played"] == 0
        assert stats.json()["scoring_avg"] is None
        assert feed.json()["matches"] == []
