"""Tests para Scoring DTOs."""

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.scoring_dto import (
    DecidedResultDTO,
    HoleInfoDTO,
    HoleResultDTO,
    HoleScoreEntryDTO,
    LeaderboardMatchDTO,
    LeaderboardPlayerDTO,
    LeaderboardResponseDTO,
    MarkerAssignmentResponseDTO,
    MatchStandingDTO,
    PlayerHoleScoreDTO,
    RoundInfoDTO,
    ScorecardResultDTO,
    ScorecardStatsDTO,
    ScoringPlayerDTO,
    ScoringViewResponseDTO,
    SubmitHoleScoreBodyDTO,
    SubmitScorecardResponseDTO,
)


class TestSubmitHoleScoreBodyDTO:
    def test_valid_body(self):
        dto = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id="abc", marked_score=4)
        assert dto.own_score == 5
        assert dto.marked_score == 4

    def test_null_scores(self):
        dto = SubmitHoleScoreBodyDTO(own_score=None, marked_player_id="abc", marked_score=None)
        assert dto.own_score is None
        assert dto.marked_score is None

    def test_score_below_1_raises(self):
        with pytest.raises(ValidationError):
            SubmitHoleScoreBodyDTO(own_score=0, marked_player_id="abc", marked_score=5)

    def test_score_above_9_raises(self):
        with pytest.raises(ValidationError):
            SubmitHoleScoreBodyDTO(own_score=10, marked_player_id="abc", marked_score=5)

    def test_min_score(self):
        dto = SubmitHoleScoreBodyDTO(own_score=1, marked_player_id="abc", marked_score=1)
        assert dto.own_score == 1

    def test_max_score(self):
        dto = SubmitHoleScoreBodyDTO(own_score=9, marked_player_id="abc", marked_score=9)
        assert dto.own_score == 9


class TestScoringViewResponseDTO:
    def test_valid_response(self):
        dto = ScoringViewResponseDTO(
            match_id="m1",
            match_number=1,
            match_format="SINGLES",
            match_status="IN_PROGRESS",
            is_decided=False,
            decided_result=None,
            round_info=RoundInfoDTO(id="r1", date="2026-03-01", session_type="MORNING", golf_course_name="Club"),
            competition_id="c1",
            team_a_name="Team A",
            team_b_name="Team B",
            marker_assignments=[],
            players=[],
            holes=[],
            scores=[],
            match_standing=MatchStandingDTO(status="AS", leading_team=None, holes_played=0, holes_remaining=18),
            scorecard_submitted_by=[],
        )
        assert dto.match_id == "m1"
        assert dto.is_decided is False


class TestLeaderboardResponseDTO:
    def test_valid_leaderboard(self):
        dto = LeaderboardResponseDTO(
            competition_id="c1",
            competition_name="Ryder Cup",
            team_a_name="Team A",
            team_b_name="Team B",
            team_a_points=3.5,
            team_b_points=2.5,
            matches=[],
        )
        assert dto.team_a_points == 3.5


class TestSubmitScorecardResponseDTO:
    def test_valid_response(self):
        dto = SubmitScorecardResponseDTO(
            match_id="m1",
            submitted_by="u1",
            result=ScorecardResultDTO(winner="A", score="3&2", team_a_points=1.0, team_b_points=0.0),
            stats=ScorecardStatsDTO(player_gross_total=82, player_net_total=72, holes_won=8, holes_lost=5, holes_halved=5),
            match_complete=True,
        )
        assert dto.match_complete is True
        assert dto.result.winner == "A"


class TestSubDTOs:
    def test_decided_result(self):
        dto = DecidedResultDTO(winner="A", score="3&2")
        assert dto.winner == "A"

    def test_hole_info(self):
        dto = HoleInfoDTO(hole_number=1, par=4, stroke_index=7)
        assert dto.par == 4

    def test_player_hole_score(self):
        dto = PlayerHoleScoreDTO(
            user_id="u1", own_score=5, marker_score=5,
            validation_status="match", net_score=4, strokes_received_this_hole=1,
        )
        assert dto.net_score == 4

    def test_hole_result(self):
        dto = HoleResultDTO(winner="A", standing="1UP", standing_team="A")
        assert dto.standing == "1UP"

    def test_scoring_player(self):
        dto = ScoringPlayerDTO(
            user_id="u1", user_name="Agustin", team="A",
            tee_category="AMATEUR", playing_handicap=12, strokes_received=[1, 3, 5],
        )
        assert dto.playing_handicap == 12

    def test_marker_assignment_response(self):
        dto = MarkerAssignmentResponseDTO(
            scorer_user_id="u1", scorer_name="A", marks_user_id="u2", marks_name="B",
            marked_by_user_id="u2", marked_by_name="B",
        )
        assert dto.scorer_user_id == "u1"

    def test_leaderboard_player(self):
        dto = LeaderboardPlayerDTO(user_id="u1", user_name="Test")
        assert dto.user_name == "Test"

    def test_leaderboard_match(self):
        dto = LeaderboardMatchDTO(
            match_id="m1", match_number=1, match_format="SINGLES", status="IN_PROGRESS",
            team_a_players=[], team_b_players=[],
        )
        assert dto.status == "IN_PROGRESS"

    def test_hole_score_entry(self):
        dto = HoleScoreEntryDTO(hole_number=1, player_scores=[], hole_result=None)
        assert dto.hole_number == 1

    def test_match_standing(self):
        dto = MatchStandingDTO(status="2UP", leading_team="A", holes_played=10, holes_remaining=8)
        assert dto.holes_remaining == 8
