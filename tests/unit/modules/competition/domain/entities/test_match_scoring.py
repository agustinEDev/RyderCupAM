"""Tests para Match Entity - Extension de scoring."""

import pytest

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.marker_assignment import (
    MarkerAssignment,
)
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_color=TeeColor.YELLOW,
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
            MarkerAssignment(
                scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id
            ),
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
        match.submit_scorecard(a.user_id, MatchFormat.SINGLES)
        assert match.has_submitted_scorecard(a.user_id, MatchFormat.SINGLES)
        assert not match.has_submitted_scorecard(b.user_id, MatchFormat.SINGLES)

    def test_all_scorecards_submitted(self):
        a = _make_player()
        b = _make_player()
        match = _create_match(team_a=[a], team_b=[b], status=MatchStatus.IN_PROGRESS)
        match.submit_scorecard(a.user_id, MatchFormat.SINGLES)
        assert not match.all_scorecards_submitted(MatchFormat.SINGLES)
        match.submit_scorecard(b.user_id, MatchFormat.SINGLES)
        assert match.all_scorecards_submitted(MatchFormat.SINGLES)

    def test_submit_non_player_raises(self):
        match = _create_match(status=MatchStatus.IN_PROGRESS)
        with pytest.raises(ValueError, match="not a player"):
            match.submit_scorecard(UserId.generate(), MatchFormat.SINGLES)

    def test_submit_duplicate_raises(self):
        a = _make_player()
        match = _create_match(team_a=[a], team_b=[_make_player()], status=MatchStatus.IN_PROGRESS)
        match.submit_scorecard(a.user_id, MatchFormat.SINGLES)
        with pytest.raises(ValueError, match="already submitted"):
            match.submit_scorecard(a.user_id, MatchFormat.SINGLES)


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
            MarkerAssignment(
                scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
            ),
        ]
        now = datetime.now()
        match = Match.reconstruct(
            id=Match.create(
                round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b]
            ).id,
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
        assert match.has_submitted_scorecard(a.user_id, MatchFormat.SINGLES)
        assert match.is_decided is True
        assert match.decided_result["winner"] == "A"


class TestUnaTarjetaPorBandoEnFoursomes:
    """BE #377: en foursomes hay UNA bola por bando (decidido en agosto), así
    que hay una tarjeta por bando. La entrega de uno vale por los dos, y el
    partido se cierra con la de cada bando, no con las cuatro. En fourball e
    individuales, cada uno la suya, como siempre.

        #   formato    | caso                                  | esperado
        ----|----------|---------------------------------------|---------------------
        M1  foursomes  | entregó el compañero                  | el bando ya entregó
        M2  foursomes  | el compañero intenta entregar         | se rechaza
        M3  foursomes  | una por bando                         | todas entregadas
        M4  fourball   | una por bando                         | no basta
        M5  foursomes  | la lista para la pantalla             | salen los dos del bando
    """

    def _parejas(self):
        a1, a2, b1, b2 = (_make_player() for _ in range(4))
        return _create_match(team_a=[a1, a2], team_b=[b1, b2]), a1, a2, b1, b2

    def test_m1_si_entrego_el_companero_el_bando_ya_entrego(self):
        match, a1, a2, _, _ = self._parejas()

        match.submit_scorecard(a1.user_id, MatchFormat.FOURSOMES)

        assert match.has_submitted_scorecard(a2.user_id, MatchFormat.FOURSOMES)

    def test_m2_el_companero_no_la_entrega_otra_vez(self):
        match, a1, a2, _, _ = self._parejas()
        match.submit_scorecard(a1.user_id, MatchFormat.FOURSOMES)

        with pytest.raises(ValueError):
            match.submit_scorecard(a2.user_id, MatchFormat.FOURSOMES)

    def test_m3_con_la_de_cada_bando_estan_todas(self):
        match, a1, _, b1, _ = self._parejas()
        match.submit_scorecard(a1.user_id, MatchFormat.FOURSOMES)
        match.submit_scorecard(b1.user_id, MatchFormat.FOURSOMES)

        assert match.all_scorecards_submitted(MatchFormat.FOURSOMES)

    def test_m4_en_fourball_cada_uno_la_suya(self):
        match, a1, a2, b1, _ = self._parejas()
        match.submit_scorecard(a1.user_id, MatchFormat.FOURBALL)
        match.submit_scorecard(b1.user_id, MatchFormat.FOURBALL)

        assert not match.all_scorecards_submitted(MatchFormat.FOURBALL)
        assert not match.has_submitted_scorecard(a2.user_id, MatchFormat.FOURBALL)

    def test_m5_la_pantalla_ve_entregado_al_bando_entero(self):
        match, a1, a2, _b1, _b2 = self._parejas()
        match.submit_scorecard(a1.user_id, MatchFormat.FOURSOMES)

        entregadas = match.scorecards_submitted_by(MatchFormat.FOURSOMES)

        assert set(entregadas) == {a1.user_id, a2.user_id}
        assert set(match.scorecards_submitted_by(MatchFormat.FOURBALL)) == {a1.user_id}
