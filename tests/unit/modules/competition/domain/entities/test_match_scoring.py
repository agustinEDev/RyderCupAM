"""Tests para Match Entity - Extension de scoring."""

import pytest

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_category=TeeCategory.AMATEUR,
        strokes_received=list(strokes),
    )


def _create_match(team_a=None, team_b=None, status=None):
    """Helper para crear un Match."""
    a = team_a or [_make_player()]
    b = team_b or [_make_player()]
    match = Match.create(
        round_id=RoundId.generate(),
        match_number=1,
        team_a_players=a,
        team_b_players=b,
    )
    if status == MatchStatus.IN_PROGRESS:
        match.start()
    return match


class TestMatchConcede:
    def test_concede_from_in_progress(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        match.concede("A")
        assert match.status == MatchStatus.CONCEDED
        assert match.result["winner"] == "B"
        assert match.result["score"] == "CONCEDED"

    def test_concede_team_b(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        match.concede("B", reason="Injury")
        assert match.result["winner"] == "A"
        assert match.result["reason"] == "Injury"

    def test_concede_from_scheduled_raises(self):
        match = _create_match()
        with pytest.raises(ValueError, match="Cannot concede"):
            match.concede("A")

    def test_concede_from_completed_raises(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        match.complete({"winner": "A", "score": "1UP"})
        with pytest.raises(ValueError, match="Cannot concede"):
            match.concede("A")

    def test_concede_invalid_team_raises(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        with pytest.raises(ValueError, match="conceding_team must be"):
            match.concede("C")

    def test_concede_is_finished(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        match.concede("A")
        assert match.is_finished()


class TestMatchSetMarkerAssignments:
    def test_set_in_scheduled(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b])
        assignments = [
            MarkerAssignment(scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id),
            MarkerAssignment(scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id),
        ]
        match.set_marker_assignments(assignments)
        assert len(match.marker_assignments) == 2

    def test_set_in_progress_raises(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        with pytest.raises(ValueError, match="Cannot set marker assignments"):
            match.set_marker_assignments([])


class TestMatchSubmitScorecard:
    def test_submit_scorecard(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b], status=MatchStatus.IN_PROGRESS)
        match.submit_scorecard(a.user_id)
        assert match.has_submitted_scorecard(a.user_id)
        assert not match.has_submitted_scorecard(b.user_id)

    def test_all_scorecards_submitted(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b], status=MatchStatus.IN_PROGRESS)
        match.submit_scorecard(a.user_id)
        assert not match.all_scorecards_submitted()
        match.submit_scorecard(b.user_id)
        assert match.all_scorecards_submitted()

    def test_submit_non_player_raises(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        with pytest.raises(ValueError, match="not a player"):
            match.submit_scorecard(UserId.generate())

    def test_submit_duplicate_raises(self):
        a = _make_player()
        match = _create_match(team_a=[a], team_b=[_make_player()], status=MatchStatus.IN_PROGRESS)
        match.submit_scorecard(a.user_id)
        with pytest.raises(ValueError, match="already submitted"):
            match.submit_scorecard(a.user_id)


class TestMatchMarkDecided:
    def test_mark_decided(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        result = {"winner": "A", "score": "5&4"}
        match.mark_decided(result)
        assert match.is_decided is True
        assert match.decided_result == result

    def test_not_decided_by_default(self):
        match = _create_match()
        assert match.is_decided is False
        assert match.decided_result is None


class TestMatchPlayerQueries:
    def test_get_player_team_a(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b])
        assert match.get_player_team(a.user_id) == "A"

    def test_get_player_team_b(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b])
        assert match.get_player_team(b.user_id) == "B"

    def test_get_player_team_not_found(self):
        match = _create_match()
        assert match.get_player_team(UserId.generate()) is None

    def test_find_player_found(self):
        a = _make_player()
        match = _create_match(team_a=[a], team_b=[_make_player()])
        assert match.find_player(a.user_id) == a

    def test_find_player_not_found(self):
        match = _create_match()
        assert match.find_player(UserId.generate()) is None

    def test_get_all_player_ids(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b])
        ids = match.get_all_player_ids()
        assert set(ids) == {a.user_id, b.user_id}


class TestMatchScoringReconstruct:
    def test_reconstruct_with_scoring_fields(self):
        from datetime import datetime

        a = _make_player()
        b = _make_player()
        assignments = [
            MarkerAssignment(scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id),
        ]
        now = datetime.now()
        match = Match.reconstruct(
            id=Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b]).id,
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[a],
            team_b_players=[b],
            status=MatchStatus.IN_PROGRESS,
            handicap_strokes_given=2,
            strokes_given_to_team="A",
            result=None,
            created_at=now,
            updated_at=now,
            marker_assignments=assignments,
            scorecard_submitted_by=[a.user_id],
            is_decided=True,
            decided_result={"winner": "A", "score": "5&4"},
        )
        assert len(match.marker_assignments) == 1
        assert match.has_submitted_scorecard(a.user_id)
        assert match.is_decided is True
        assert match.decided_result["winner"] == "A"
