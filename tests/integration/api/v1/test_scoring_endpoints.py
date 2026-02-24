"""
Tests E2E para Scoring Endpoints.

Tests de integracion que verifican el flujo completo de los endpoints
de scoring incluyendo registro de scores, validacion cruzada, entrega
de tarjetas, leaderboard y concesion de partidos.
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
    set_auth_cookies,
)

# ======================================================================================
# HELPERS
# ======================================================================================


async def setup_match_in_progress(client: AsyncClient):  # noqa: PLR0915
    """
    Setup completo: crea competicion SCRATCH con 2 jugadores, 1 ronda SINGLES,
    genera partidos, inicia competicion y match. Retorna IDs necesarios.

    Returns:
        dict con: creator, player_a, player_b, competition_id, match_id, round_id
    """
    # 1. Crear usuarios
    creator = await create_authenticated_user(
        client, "sc_creator@test.com", "P@ssw0rd123!", "Creator", "Scoring"
    )
    player_a = await create_authenticated_user(
        client, "sc_player_a@test.com", "P@ssw0rd123!", "PlayerA", "TeamA"
    )
    player_b = await create_authenticated_user(
        client, "sc_player_b@test.com", "P@ssw0rd123!", "PlayerB", "TeamB"
    )
    admin = await create_admin_user(
        client, "sc_admin@test.com", "P@ssw0rd123!", "Admin", "Scoring"
    )

    # 2. Crear competicion SCRATCH
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=3)
    comp_data = {
        "name": "Scoring Test Competition",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "main_country": "ES",
        "play_mode": "SCRATCH",
        "max_players": 24,
        "team_assignment": "MANUAL",
    }
    comp = await create_competition(client, creator["cookies"], comp_data)
    comp_id = comp["id"]

    # 3. Crear y aprobar campo de golf
    gc = await create_golf_course(client, creator["cookies"])
    gc_id = gc["id"]
    await approve_golf_course(client, admin["cookies"], gc_id)

    # 4. Asociar campo a competicion
    set_auth_cookies(client, creator["cookies"])
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/golf-courses",
        json={"golf_course_id": gc_id},
    )
    assert resp.status_code == 201, f"Failed to add golf course: {resp.text}"

    # 5. Activar competicion
    await activate_competition(client, creator["cookies"], comp_id)

    # 6. Inscribir jugadores
    set_auth_cookies(client, player_a["cookies"])
    resp_a = await client.post(f"/api/v1/competitions/{comp_id}/enrollments")
    assert resp_a.status_code in (200, 201), f"Failed to enroll player_a: {resp_a.text}"
    set_auth_cookies(client, player_b["cookies"])
    resp_b = await client.post(f"/api/v1/competitions/{comp_id}/enrollments")
    assert resp_b.status_code in (200, 201), f"Failed to enroll player_b: {resp_b.text}"

    # 7. Aprobar inscripciones
    set_auth_cookies(client, creator["cookies"])
    enroll_resp = await client.get(f"/api/v1/competitions/{comp_id}/enrollments")
    assert enroll_resp.status_code == 200, f"Failed to get enrollments: {enroll_resp.text}"
    enrollments = enroll_resp.json()
    for e in enrollments:
        if e["status"] == "REQUESTED":
            await client.post(f"/api/v1/enrollments/{e['id']}/approve")

    # 8. Retirar inscripción del creator (auto-enrolled) para mantener solo 2 jugadores
    set_auth_cookies(client, creator["cookies"])
    enroll_resp2 = await client.get(f"/api/v1/competitions/{comp_id}/enrollments")
    for e in enroll_resp2.json():
        if e["user_id"] == creator["user"]["id"] and e["status"] == "APPROVED":
            await client.post(f"/api/v1/enrollments/{e['id']}/withdraw")

    # 9. Cerrar inscripciones
    await client.post(f"/api/v1/competitions/{comp_id}/close-enrollments")

    # 10. Crear ronda SINGLES (ANTES de asignar equipos para que se transicione a PENDING_MATCHES)
    set_auth_cookies(client, creator["cookies"])
    round_resp = await client.post(
        f"/api/v1/competitions/{comp_id}/rounds",
        json={
            "golf_course_id": gc_id,
            "round_date": start.isoformat(),
            "session_type": "MORNING",
            "match_format": "SINGLES",
        },
    )
    assert round_resp.status_code == 201, f"Failed to create round: {round_resp.text}"
    round_id = round_resp.json()["id"]

    # 11. Asignar equipos manualmente
    set_auth_cookies(client, creator["cookies"])
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/teams",
        json={
            "mode": "MANUAL",
            "team_a_player_ids": [player_a["user"]["id"]],
            "team_b_player_ids": [player_b["user"]["id"]],
        },
    )
    assert resp.status_code == 201, f"Failed to assign teams: {resp.text}"

    # 13. Generar partidos
    set_auth_cookies(client, creator["cookies"])
    gen_resp = await client.post(
        f"/api/v1/competitions/rounds/{round_id}/matches/generate",
        json={},
    )
    assert gen_resp.status_code == 201, f"Failed to generate matches: {gen_resp.text}"

    # 14. Obtener match_id del schedule
    set_auth_cookies(client, creator["cookies"])
    sched_resp = await client.get(f"/api/v1/competitions/{comp_id}/schedule")
    assert sched_resp.status_code == 200
    schedule = sched_resp.json()
    match_id = schedule["days"][0]["rounds"][0]["matches"][0]["id"]

    # 15. Iniciar competicion
    set_auth_cookies(client, creator["cookies"])
    start_resp = await client.post(f"/api/v1/competitions/{comp_id}/start")
    assert start_resp.status_code == 200, f"Failed to start competition: {start_resp.text}"

    # 16. Iniciar partido (pre-crea HoleScores)
    set_auth_cookies(client, creator["cookies"])
    status_resp = await client.put(
        f"/api/v1/competitions/matches/{match_id}/status",
        json={"action": "START"},
    )
    assert status_resp.status_code == 200, f"Failed to start match: {status_resp.text}"

    return {
        "creator": creator,
        "player_a": player_a,
        "player_b": player_b,
        "admin": admin,
        "competition_id": comp_id,
        "match_id": match_id,
        "round_id": round_id,
    }


# ======================================================================================
# SCORING VIEW TESTS
# ======================================================================================


class TestGetScoringView:
    """Tests para GET /api/v1/competitions/matches/{match_id}/scoring-view"""

    @pytest.mark.asyncio
    async def test_get_scoring_view_success(self, client: AsyncClient):
        """Obtener vista de scoring retorna 200 con estructura completa."""
        ctx = await setup_match_in_progress(client)

        set_auth_cookies(client, ctx["player_a"]["cookies"])
        response = await client.get(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scoring-view"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["match_id"] == ctx["match_id"]
        assert data["match_status"] == "IN_PROGRESS"
        assert data["match_format"] == "SINGLES"
        assert data["is_decided"] is False
        assert len(data["players"]) == 2
        assert len(data["holes"]) == 18
        assert len(data["scores"]) == 18
        assert len(data["marker_assignments"]) > 0
        assert data["match_standing"]["holes_played"] == 0
        assert data["match_standing"]["holes_remaining"] == 18
        assert data["scorecard_submitted_by"] == []

    @pytest.mark.asyncio
    async def test_get_scoring_view_not_found(self, client: AsyncClient):
        """Scoring view de partido inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "sv_notfound@test.com", "P@ssw0rd123!", "Not", "Found"
        )
        fake_id = "00000000-0000-0000-0000-000000000000"

        set_auth_cookies(client, user["cookies"])
        response = await client.get(
            f"/api/v1/competitions/matches/{fake_id}/scoring-view"
        )

        assert response.status_code == 404


# ======================================================================================
# SUBMIT HOLE SCORE TESTS
# ======================================================================================


class TestSubmitHoleScore:
    """Tests para POST /api/v1/competitions/matches/{match_id}/scores/holes/{hole_number}"""

    @pytest.mark.asyncio
    async def test_submit_hole_score_success(self, client: AsyncClient):
        """Registrar score de hoyo retorna 200 con scoring view actualizado."""
        ctx = await setup_match_in_progress(client)
        player_a_id = ctx["player_a"]["user"]["id"]
        player_b_id = ctx["player_b"]["user"]["id"]

        # Player A submits own score and marks Player B
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 4,
                "marked_player_id": player_b_id,
                "marked_score": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["match_id"] == ctx["match_id"]

        # Find player A's score for hole 1
        hole_1 = next(s for s in data["scores"] if s["hole_number"] == 1)
        a_score = next(
            ps for ps in hole_1["player_scores"] if ps["user_id"] == player_a_id
        )
        assert a_score["own_score"] == 4

        # Player B should have marker_score set by A
        b_score = next(
            ps for ps in hole_1["player_scores"] if ps["user_id"] == player_b_id
        )
        assert b_score["marker_score"] == 5

    @pytest.mark.asyncio
    async def test_cross_validation_produces_match(self, client: AsyncClient):
        """Cuando ambos jugadores registran el mismo score, validation_status es MATCH."""
        ctx = await setup_match_in_progress(client)
        player_a_id = ctx["player_a"]["user"]["id"]
        player_b_id = ctx["player_b"]["user"]["id"]

        # Player A: own=4, marks B=5
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 4,
                "marked_player_id": player_b_id,
                "marked_score": 5,
            },
        )

        # Player B: own=5, marks A=4
        set_auth_cookies(client, ctx["player_b"]["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 5,
                "marked_player_id": player_a_id,
                "marked_score": 4,
            },
        )

        assert response.status_code == 200
        data = response.json()
        hole_1 = next(s for s in data["scores"] if s["hole_number"] == 1)

        # Both should be match (lowercase from DTO serialization)
        for ps in hole_1["player_scores"]:
            assert ps["validation_status"] == "match"

    @pytest.mark.asyncio
    async def test_cross_validation_produces_mismatch(self, client: AsyncClient):
        """Cuando los scores no coinciden, validation_status es MISMATCH."""
        ctx = await setup_match_in_progress(client)
        player_a_id = ctx["player_a"]["user"]["id"]
        player_b_id = ctx["player_b"]["user"]["id"]

        # Player A: own=4, marks B=5
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 4,
                "marked_player_id": player_b_id,
                "marked_score": 5,
            },
        )

        # Player B: own=6, marks A=3 (different from what A entered)
        set_auth_cookies(client, ctx["player_b"]["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 6,
                "marked_player_id": player_a_id,
                "marked_score": 3,
            },
        )

        assert response.status_code == 200
        data = response.json()
        hole_1 = next(s for s in data["scores"] if s["hole_number"] == 1)

        # Both should be mismatch (lowercase from DTO serialization)
        for ps in hole_1["player_scores"]:
            assert ps["validation_status"] == "mismatch"

    @pytest.mark.asyncio
    async def test_submit_hole_score_non_player_returns_403(self, client: AsyncClient):
        """Jugador no perteneciente al partido recibe 403."""
        ctx = await setup_match_in_progress(client)
        outsider = await create_authenticated_user(
            client, "outsider@test.com", "P@ssw0rd123!", "Out", "Sider"
        )

        set_auth_cookies(client, outsider["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 4,
                "marked_player_id": ctx["player_b"]["user"]["id"],
                "marked_score": 5,
            },
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_submit_hole_score_invalid_hole_returns_400(self, client: AsyncClient):
        """Hoyo fuera de rango retorna 400."""
        ctx = await setup_match_in_progress(client)

        set_auth_cookies(client, ctx["player_a"]["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/19",
            json={
                "own_score": 4,
                "marked_player_id": ctx["player_b"]["user"]["id"],
                "marked_score": 5,
            },
        )

        assert response.status_code == 400


# ======================================================================================
# SUBMIT SCORECARD TESTS
# ======================================================================================


class TestSubmitScorecard:
    """Tests para POST /api/v1/competitions/matches/{match_id}/scorecard/submit"""

    @pytest.mark.asyncio
    async def test_submit_scorecard_all_validated_success(self, client: AsyncClient):
        """Entregar tarjeta con todos los hoyos validados retorna 200."""
        ctx = await setup_match_in_progress(client)
        player_a_id = ctx["player_a"]["user"]["id"]
        player_b_id = ctx["player_b"]["user"]["id"]

        # Submit matching scores for all 18 holes
        for hole in range(1, 19):
            set_auth_cookies(client, ctx["player_a"]["cookies"])
            await client.post(
                f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/{hole}",
                json={
                    "own_score": 4,
                    "marked_player_id": player_b_id,
                    "marked_score": 4,
                },
            )
            set_auth_cookies(client, ctx["player_b"]["cookies"])
            await client.post(
                f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/{hole}",
                json={
                    "own_score": 4,
                    "marked_player_id": player_a_id,
                    "marked_score": 4,
                },
            )

        # Player A submits scorecard
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scorecard/submit"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["match_id"] == ctx["match_id"]
        assert data["submitted_by"] == player_a_id
        assert data["match_complete"] is False  # Only 1 of 2 submitted

    @pytest.mark.asyncio
    async def test_submit_scorecard_unvalidated_holes_returns_400(
        self, client: AsyncClient
    ):
        """Entregar tarjeta con hoyos sin validar retorna 400."""
        ctx = await setup_match_in_progress(client)
        player_b_id = ctx["player_b"]["user"]["id"]

        # Only submit score for hole 1 (just player A, no cross-validation)
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/1",
            json={
                "own_score": 4,
                "marked_player_id": player_b_id,
                "marked_score": 5,
            },
        )

        # Try to submit scorecard (validation_status is PENDING for most holes)
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scorecard/submit"
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_all_scorecards_triggers_match_completion(self, client: AsyncClient):
        """Cuando todos los jugadores entregan tarjeta, el partido se completa."""
        ctx = await setup_match_in_progress(client)
        player_a_id = ctx["player_a"]["user"]["id"]
        player_b_id = ctx["player_b"]["user"]["id"]

        # Submit matching scores for all 18 holes
        for hole in range(1, 19):
            set_auth_cookies(client, ctx["player_a"]["cookies"])
            await client.post(
                f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/{hole}",
                json={
                    "own_score": 4,
                    "marked_player_id": player_b_id,
                    "marked_score": 5,
                },
            )
            set_auth_cookies(client, ctx["player_b"]["cookies"])
            await client.post(
                f"/api/v1/competitions/matches/{ctx['match_id']}/scores/holes/{hole}",
                json={
                    "own_score": 5,
                    "marked_player_id": player_a_id,
                    "marked_score": 4,
                },
            )

        # Player A submits
        set_auth_cookies(client, ctx["player_a"]["cookies"])
        resp_a = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scorecard/submit"
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["match_complete"] is False

        # Player B submits — should trigger match completion
        set_auth_cookies(client, ctx["player_b"]["cookies"])
        resp_b = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scorecard/submit"
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["match_complete"] is True

    @pytest.mark.asyncio
    async def test_submit_scorecard_non_player_returns_403(self, client: AsyncClient):
        """No jugador intentando entregar tarjeta recibe 403."""
        ctx = await setup_match_in_progress(client)
        outsider = await create_authenticated_user(
            client, "sc_outsider@test.com", "P@ssw0rd123!", "Out", "Sider"
        )

        set_auth_cookies(client, outsider["cookies"])
        response = await client.post(
            f"/api/v1/competitions/matches/{ctx['match_id']}/scorecard/submit"
        )

        assert response.status_code == 403


# ======================================================================================
# LEADERBOARD TESTS
# ======================================================================================


class TestGetLeaderboard:
    """Tests para GET /api/v1/competitions/{competition_id}/leaderboard"""

    @pytest.mark.asyncio
    async def test_get_leaderboard_success(self, client: AsyncClient):
        """Obtener leaderboard retorna 200 con estructura completa."""
        ctx = await setup_match_in_progress(client)

        set_auth_cookies(client, ctx["player_a"]["cookies"])
        response = await client.get(
            f"/api/v1/competitions/{ctx['competition_id']}/leaderboard"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == ctx["competition_id"]
        assert "team_a_points" in data
        assert "team_b_points" in data
        assert len(data["matches"]) >= 1

        # Verify match structure
        match = data["matches"][0]
        assert match["status"] == "IN_PROGRESS"
        assert len(match["team_a_players"]) >= 1
        assert len(match["team_b_players"]) >= 1

    @pytest.mark.asyncio
    async def test_get_leaderboard_not_found(self, client: AsyncClient):
        """Leaderboard de competicion inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "lb_notfound@test.com", "P@ssw0rd123!", "Not", "Found"
        )
        fake_id = "00000000-0000-0000-0000-000000000000"

        set_auth_cookies(client, user["cookies"])
        response = await client.get(
            f"/api/v1/competitions/{fake_id}/leaderboard"
        )

        assert response.status_code == 404


# ======================================================================================
# CONCEDE MATCH TESTS
# ======================================================================================


class TestConcedeMatch:
    """Tests para PUT /api/v1/competitions/matches/{match_id}/concede"""

    @pytest.mark.asyncio
    async def test_concede_match_by_creator(self, client: AsyncClient):
        """Creator puede conceder cualquier equipo."""
        ctx = await setup_match_in_progress(client)

        set_auth_cookies(client, ctx["creator"]["cookies"])
        response = await client.put(
            f"/api/v1/competitions/matches/{ctx['match_id']}/concede",
            json={"conceding_team": "A", "reason": "Team A concedes"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concede_match_non_player_returns_403(self, client: AsyncClient):
        """No jugador ni creator intentando conceder recibe 403."""
        ctx = await setup_match_in_progress(client)
        outsider = await create_authenticated_user(
            client, "cc_outsider@test.com", "P@ssw0rd123!", "Out", "Sider"
        )

        set_auth_cookies(client, outsider["cookies"])
        response = await client.put(
            f"/api/v1/competitions/matches/{ctx['match_id']}/concede",
            json={"conceding_team": "A"},
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_concede_match_not_found(self, client: AsyncClient):
        """Conceder partido inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "cc_notfound@test.com", "P@ssw0rd123!", "Not", "Found"
        )
        fake_id = "00000000-0000-0000-0000-000000000000"

        set_auth_cookies(client, user["cookies"])
        response = await client.put(
            f"/api/v1/competitions/matches/{fake_id}/concede",
            json={"conceding_team": "A"},
        )

        assert response.status_code == 404
