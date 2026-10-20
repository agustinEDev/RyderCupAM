"""Tests para ScoringService - Servicio de dominio de scoring."""

import pytest

from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.value_objects.match_format import MatchFormat


@pytest.fixture
def service():
    return ScoringService()


def test_es_un_match_play_con_las_reglas_de_la_ryder():
    """
    Las reglas del match play viven en shared (RyderCupAM#165) y ScoringService
    añade lo de la Ryder: así competición las sigue usando sin cambiar.
    """
    assert isinstance(ScoringService(), MatchPlayScoring)


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_color=TeeColor.YELLOW,
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
        result = service.get_affected_player_ids(
            (scorer,), (_make_player(),), scorer.user_id, MatchFormat.SINGLES
        )
        assert result == [scorer.user_id]

    def test_fourball_returns_only_scorer(self, service):
        a1, a2 = _make_player(), _make_player()
        result = service.get_affected_player_ids(
            (a1, a2), (_make_player(), _make_player()), a1.user_id, MatchFormat.FOURBALL
        )
        assert result == [a1.user_id]

    def test_foursomes_returns_both_teammates(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_player_ids(
            (a1, a2), (b1, b2), a1.user_id, MatchFormat.FOURSOMES
        )
        assert set(result) == {a1.user_id, a2.user_id}

    def test_foursomes_returns_team_b_when_scorer_is_b(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_player_ids(
            (a1, a2), (b1, b2), b2.user_id, MatchFormat.FOURSOMES
        )
        assert set(result) == {b1.user_id, b2.user_id}


class TestAffectedMarkedPlayerIds:
    def test_singles_returns_only_marked(self, service):
        marked = _make_player()
        result = service.get_affected_marked_player_ids(
            (_make_player(),), (marked,), marked.user_id, MatchFormat.SINGLES
        )
        assert result == [marked.user_id]

    def test_foursomes_returns_both_marked_teammates(self, service):
        a1, a2 = _make_player(), _make_player()
        b1, b2 = _make_player(), _make_player()
        result = service.get_affected_marked_player_ids(
            (a1, a2), (b1, b2), b1.user_id, MatchFormat.FOURSOMES
        )
        assert set(result) == {b1.user_id, b2.user_id}


# ==================== Hole Winner ====================


class TestCalculateRyderCupPoints:
    def test_a_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "A", "score": "3&2"}, "COMPLETED")
        assert points == {"team_a": 1.0, "team_b": 0.0}

    def test_b_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "B", "score": "1UP"}, "COMPLETED")
        assert points == {"team_a": 0.0, "team_b": 1.0}

    def test_halved(self, service):
        points = service.calculate_ryder_cup_points(
            {"winner": "HALVED", "score": "AS"}, "COMPLETED"
        )
        assert points == {"team_a": 0.5, "team_b": 0.5}

    def test_no_result(self, service):
        points = service.calculate_ryder_cup_points(None, "IN_PROGRESS")
        assert points == {"team_a": 0.0, "team_b": 0.0}

    def test_conceded_b_wins(self, service):
        points = service.calculate_ryder_cup_points(
            {"winner": "B", "score": "CONCEDED"}, "CONCEDED"
        )
        assert points == {"team_a": 0.0, "team_b": 1.0}

    def test_walkover_a_wins(self, service):
        points = service.calculate_ryder_cup_points({"winner": "A", "score": "W/O"}, "WALKOVER")
        assert points == {"team_a": 1.0, "team_b": 0.0}
