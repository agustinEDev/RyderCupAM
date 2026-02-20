"""Tests para ScoringService - Servicio de dominio de scoring."""

import pytest

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


@pytest.fixture
def service():
    return ScoringService()


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_category=TeeCategory.AMATEUR,
        strokes_received=list(strokes),
    )


# ==================== Marker Assignments ====================


class TestSinglesMarkerAssignments:
    def test_generates_two_reciprocal_assignments(self, service):
        a = _make_player()
        b = _make_player()
        assignments = service.generate_marker_assignments((a,), (b,), MatchFormat.SINGLES)
        assert len(assignments) == 2

    def test_a_marks_b(self, service):
        a = _make_player()
        b = _make_player()
        assignments = service.generate_marker_assignments((a,), (b,), MatchFormat.SINGLES)
        a_assignment = next(ma for ma in assignments if ma.scorer_user_id == a.user_id)
        assert a_assignment.marks_user_id == b.user_id

    def test_b_marks_a(self, service):
        a = _make_player()
        b = _make_player()
        assignments = service.generate_marker_assignments((a,), (b,), MatchFormat.SINGLES)
        b_assignment = next(ma for ma in assignments if ma.scorer_user_id == b.user_id)
        assert b_assignment.marks_user_id == a.user_id

    def test_a_is_marked_by_b(self, service):
        a = _make_player()
        b = _make_player()
        assignments = service.generate_marker_assignments((a,), (b,), MatchFormat.SINGLES)
        a_assignment = next(ma for ma in assignments if ma.scorer_user_id == a.user_id)
        assert a_assignment.marked_by_user_id == b.user_id


class TestFourballMarkerAssignments:
    def test_generates_four_assignments(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        assignments = service.generate_marker_assignments((a1, a2), (b1, b2), MatchFormat.FOURBALL)
        assert len(assignments) == 4

    def test_a1_marks_b1(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        assignments = service.generate_marker_assignments((a1, a2), (b1, b2), MatchFormat.FOURBALL)
        a1_assignment = next(ma for ma in assignments if ma.scorer_user_id == a1.user_id)
        assert a1_assignment.marks_user_id == b1.user_id

    def test_a2_marks_b2(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        assignments = service.generate_marker_assignments((a1, a2), (b1, b2), MatchFormat.FOURBALL)
        a2_assignment = next(ma for ma in assignments if ma.scorer_user_id == a2.user_id)
        assert a2_assignment.marks_user_id == b2.user_id

    def test_cross_team_markers(self, service):
        """Marcadores siempre del equipo contrario."""
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        team_a_ids = {a1.user_id, a2.user_id}
        team_b_ids = {b1.user_id, b2.user_id}
        assignments = service.generate_marker_assignments((a1, a2), (b1, b2), MatchFormat.FOURBALL)
        for ma in assignments:
            if ma.scorer_user_id in team_a_ids:
                assert ma.marks_user_id in team_b_ids
            else:
                assert ma.marks_user_id in team_a_ids


class TestFoursomesMarkerAssignments:
    def test_generates_four_assignments(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        assignments = service.generate_marker_assignments((a1, a2), (b1, b2), MatchFormat.FOURSOMES)
        assert len(assignments) == 4


# ==================== Affected Player IDs ====================


class TestAffectedPlayerIds:
    def test_singles_returns_only_scorer(self, service):
        scorer = _make_player()
        result = service.get_affected_player_ids((scorer,), (_make_player(),), scorer.user_id, MatchFormat.SINGLES)
        assert result == [scorer.user_id]

    def test_fourball_returns_only_scorer(self, service):
        a1, a2 = _make_player(), _make_player()
        result = service.get_affected_player_ids((a1, a2), (_make_player(), _make_player()), a1.user_id, MatchFormat.FOURBALL)
        assert result == [a1.user_id]

    def test_foursomes_returns_both_teammates(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_player_ids((a1, a2), (b1, b2), a1.user_id, MatchFormat.FOURSOMES)
        assert set(result) == {a1.user_id, a2.user_id}

    def test_foursomes_returns_team_b_when_scorer_is_b(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_player_ids((a1, a2), (b1, b2), b2.user_id, MatchFormat.FOURSOMES)
        assert set(result) == {b1.user_id, b2.user_id}


class TestAffectedMarkedPlayerIds:
    def test_singles_returns_only_marked(self, service):
        marked = _make_player()
        result = service.get_affected_marked_player_ids((_make_player(),), (marked,), marked.user_id, MatchFormat.SINGLES)
        assert result == [marked.user_id]

    def test_foursomes_returns_both_marked_teammates(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_marked_player_ids((a1, a2), (b1, b2), b1.user_id, MatchFormat.FOURSOMES)
        assert set(result) == {b1.user_id, b2.user_id}


# ==================== Hole Winner ====================


class TestCalculateHoleWinner:
    def test_a_wins_lower_net(self, service):
        result = service.calculate_hole_winner([3], [4], MatchFormat.SINGLES)
        assert result == "A"

    def test_b_wins_lower_net(self, service):
        result = service.calculate_hole_winner([5], [4], MatchFormat.SINGLES)
        assert result == "B"

    def test_halved_equal_net(self, service):
        result = service.calculate_hole_winner([4], [4], MatchFormat.SINGLES)
        assert result == "HALVED"

    def test_both_picked_up_halved(self, service):
        result = service.calculate_hole_winner([None], [None], MatchFormat.SINGLES)
        assert result == "HALVED"

    def test_a_picked_up_b_wins(self, service):
        result = service.calculate_hole_winner([None], [4], MatchFormat.SINGLES)
        assert result == "B"

    def test_b_picked_up_a_wins(self, service):
        result = service.calculate_hole_winner([4], [None], MatchFormat.SINGLES)
        assert result == "A"

    def test_fourball_best_ball_a_wins(self, service):
        """Mejor bola del equipo A gana."""
        result = service.calculate_hole_winner([3, 5], [4, 4], MatchFormat.FOURBALL)
        assert result == "A"

    def test_fourball_best_ball_halved(self, service):
        result = service.calculate_hole_winner([3, 5], [4, 3], MatchFormat.FOURBALL)
        assert result == "HALVED"

    def test_fourball_one_picked_up(self, service):
        """Un jugador picked up, el otro cuenta."""
        result = service.calculate_hole_winner([None, 4], [5, 5], MatchFormat.FOURBALL)
        assert result == "A"

    def test_foursomes_single_score(self, service):
        result = service.calculate_hole_winner([3], [4], MatchFormat.FOURSOMES)
        assert result == "A"


# ==================== Match Standing ====================


class TestCalculateMatchStanding:
    def test_all_square(self, service):
        standing = service.calculate_match_standing(["A", "B", "HALVED"])
        assert standing["status"] == "AS"
        assert standing["leading_team"] is None
        assert standing["holes_played"] == 3
        assert standing["holes_remaining"] == 15

    def test_a_leading(self, service):
        standing = service.calculate_match_standing(["A", "A", "B"])
        assert standing["status"] == "1UP"
        assert standing["leading_team"] == "A"

    def test_b_leading(self, service):
        standing = service.calculate_match_standing(["B", "B", "B", "A"])
        assert standing["status"] == "2UP"
        assert standing["leading_team"] == "B"

    def test_empty_holes(self, service):
        standing = service.calculate_match_standing([])
        assert standing["status"] == "AS"
        assert standing["holes_played"] == 0
        assert standing["holes_remaining"] == 18


# ==================== Match Decided ====================


class TestIsMatchDecided:
    def test_not_decided_all_square(self, service):
        standing = {"status": "AS", "leading_team": None, "holes_played": 9, "holes_remaining": 9}
        assert not service.is_match_decided(standing)

    def test_not_decided_lead_equals_remaining(self, service):
        standing = {"status": "3UP", "leading_team": "A", "holes_played": 15, "holes_remaining": 3}
        assert not service.is_match_decided(standing)

    def test_decided_lead_exceeds_remaining(self, service):
        standing = {"status": "5UP", "leading_team": "A", "holes_played": 14, "holes_remaining": 4}
        assert service.is_match_decided(standing)

    def test_decided_one_hole_left(self, service):
        standing = {"status": "2UP", "leading_team": "B", "holes_played": 17, "holes_remaining": 1}
        assert service.is_match_decided(standing)


# ==================== Format Decided Result ====================


class TestFormatDecidedResult:
    def test_early_termination(self, service):
        # A leads 5-0 after 14 holes → 5&4
        holes = ["A"] * 5 + ["HALVED"] * 9
        result = service.format_decided_result(holes)
        assert result["winner"] == "A"
        assert result["score"] == "5&4"

    def test_one_up_after_18(self, service):
        holes = ["A"] * 10 + ["B"] * 8
        result = service.format_decided_result(holes)
        assert result["winner"] == "A"
        assert result["score"] == "2UP"

    def test_halved_after_18(self, service):
        holes = ["A"] * 9 + ["B"] * 9
        result = service.format_decided_result(holes)
        assert result["winner"] == "HALVED"
        assert result["score"] == "AS"

    def test_3_and_2(self, service):
        # A wins 3 more than B with 2 remaining
        holes = ["A"] * 8 + ["B"] * 5 + ["HALVED"] * 3
        result = service.format_decided_result(holes)
        assert result["winner"] == "A"
        assert result["score"] == "3&2"


# ==================== Ryder Cup Points ====================


class TestCalculateRyderCupPoints:
    def test_a_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "A", "score": "3&2"}, "COMPLETED")
        assert points == {"team_a": 1.0, "team_b": 0.0}

    def test_b_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "B", "score": "1UP"}, "COMPLETED")
        assert points == {"team_a": 0.0, "team_b": 1.0}

    def test_halved(self, service):
        points = service.calculate_ryder_cup_points({"winner": "HALVED", "score": "AS"}, "COMPLETED")
        assert points == {"team_a": 0.5, "team_b": 0.5}

    def test_no_result(self, service):
        points = service.calculate_ryder_cup_points(None, "IN_PROGRESS")
        assert points == {"team_a": 0.0, "team_b": 0.0}

    def test_conceded_b_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "B", "score": "CONCEDED"}, "CONCEDED")
        assert points == {"team_a": 0.0, "team_b": 1.0}

    def test_walkover_a_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "A", "score": "W/O"}, "WALKOVER")
        assert points == {"team_a": 1.0, "team_b": 0.0}
