"""Tests para Match entity."""

from datetime import datetime

import pytest

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


def create_match_player(handicap: int = 10) -> MatchPlayer:
    """Helper para crear MatchPlayer."""
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=handicap,
        tee_category=TeeCategory.AMATEUR_MALE,
        strokes_received=list(range(1, handicap + 1)) if handicap > 0 else [],
    )


class TestMatchCreate:
    """Tests para creación de Match"""

    def test_create_singles_match(self):
        """Crea un partido de SINGLES (1 vs 1)."""
        round_id = RoundId.generate()
        player_a = create_match_player(handicap=10)
        player_b = create_match_player(handicap=15)

        match = Match.create(
            round_id=round_id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        assert match.id is not None
        assert match.round_id == round_id
        assert match.match_number == 1
        assert len(match.team_a_players) == 1
        assert len(match.team_b_players) == 1
        assert match.status == MatchStatus.SCHEDULED

    def test_create_fourball_match(self):
        """Crea un partido de FOURBALL (2 vs 2)."""
        round_id = RoundId.generate()
        team_a = [create_match_player(10), create_match_player(12)]
        team_b = [create_match_player(8), create_match_player(14)]

        match = Match.create(
            round_id=round_id,
            match_number=2,
            team_a_players=team_a,
            team_b_players=team_b,
        )

        assert len(match.team_a_players) == 2
        assert len(match.team_b_players) == 2

    def test_create_calculates_handicap_strokes(self):
        """create() calcula golpes de ventaja automáticamente."""
        player_a = create_match_player(handicap=10)  # Team A total: 10
        player_b = create_match_player(handicap=18)  # Team B total: 18

        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        assert match.handicap_strokes_given == 8  # |10 - 18| = 8
        assert match.strokes_given_to_team == "B"  # B tiene más handicap

    def test_create_with_equal_handicaps(self):
        """Sin ventaja cuando handicaps son iguales."""
        player_a = create_match_player(handicap=12)
        player_b = create_match_player(handicap=12)

        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        assert match.handicap_strokes_given == 0
        assert match.strokes_given_to_team == ""

    def test_create_with_unequal_teams_raises(self):
        """Error si equipos tienen diferente número de jugadores."""
        with pytest.raises(ValueError, match="Teams must have equal players"):
            Match.create(
                round_id=RoundId.generate(),
                match_number=1,
                team_a_players=[create_match_player()],
                team_b_players=[create_match_player(), create_match_player()],
            )

    def test_create_with_empty_teams_raises(self):
        """Error si equipos están vacíos."""
        with pytest.raises(ValueError, match="Teams cannot be empty"):
            Match.create(
                round_id=RoundId.generate(),
                match_number=1,
                team_a_players=[],
                team_b_players=[],
            )

    def test_create_with_invalid_match_number_raises(self):
        """Error si match_number < 1."""
        with pytest.raises(ValueError, match="match_number must be >= 1"):
            Match.create(
                round_id=RoundId.generate(),
                match_number=0,
                team_a_players=[create_match_player()],
                team_b_players=[create_match_player()],
            )


class TestMatchStatusTransitions:
    """Tests para transiciones de estado"""

    def test_start_from_scheduled(self):
        """SCHEDULED → IN_PROGRESS."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        match.start()

        assert match.status == MatchStatus.IN_PROGRESS

    def test_start_from_wrong_status_raises(self):
        """start() desde estado incorrecto lanza error."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.COMPLETED,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result={"winner": "A", "score": "2&1"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with pytest.raises(ValueError, match="Expected SCHEDULED"):
            match.start()

    def test_complete_from_in_progress(self):
        """IN_PROGRESS → COMPLETED con resultado."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.IN_PROGRESS,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        match.complete({"winner": "A", "score": "3&2"})

        assert match.status == MatchStatus.COMPLETED
        assert match.result["winner"] == "A"

    def test_complete_with_halved_result(self):
        """Partido puede terminar empatado (HALVED)."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.IN_PROGRESS,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        match.complete({"winner": "HALVED", "score": "AS"})

        assert match.result["winner"] == "HALVED"


class TestMatchWalkover:
    """Tests para walkover"""

    def test_declare_walkover_from_scheduled(self):
        """Walkover desde SCHEDULED."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        match.declare_walkover("A", reason="Team B no-show")

        assert match.status == MatchStatus.WALKOVER
        assert match.result["winner"] == "A"
        assert match.result["score"] == "W/O"
        assert match.result["reason"] == "Team B no-show"

    def test_declare_walkover_from_in_progress(self):
        """Walkover desde IN_PROGRESS."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.IN_PROGRESS,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        match.declare_walkover("B")

        assert match.status == MatchStatus.WALKOVER
        assert match.result["winner"] == "B"

    def test_declare_walkover_invalid_team_raises(self):
        """Error si equipo ganador no es A o B."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        with pytest.raises(ValueError, match="must be 'A' or 'B'"):
            match.declare_walkover("C")


class TestMatchQueryMethods:
    """Tests para métodos de consulta"""

    def test_is_finished_completed(self):
        """COMPLETED es estado finalizado."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.COMPLETED,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result={"winner": "A"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert match.is_finished() is True

    def test_is_finished_scheduled(self):
        """SCHEDULED no es estado finalizado."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        assert match.is_finished() is False

    def test_get_winner_returns_winner_when_finished(self):
        """get_winner retorna ganador si terminado."""
        match = Match.reconstruct(
            id=MatchId.generate(),
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.COMPLETED,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result={"winner": "B", "score": "1UP"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert match.get_winner() == "B"

    def test_get_winner_returns_none_when_not_finished(self):
        """get_winner retorna None si no terminado."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        assert match.get_winner() is None

    def test_team_handicap_totals(self):
        """Calcula totales de handicap por equipo."""
        team_a = [create_match_player(10), create_match_player(15)]
        team_b = [create_match_player(8), create_match_player(12)]

        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=team_a,
            team_b_players=team_b,
        )

        assert match.team_a_total_handicap() == 25
        assert match.team_b_total_handicap() == 20


class TestMatchEquality:
    """Tests para igualdad y hash"""

    def test_matches_with_same_id_are_equal(self):
        """Matches con mismo ID son iguales."""
        match_id = MatchId.generate()
        now = datetime.now()

        match1 = Match.reconstruct(
            id=match_id,
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.SCHEDULED,
            handicap_strokes_given=0,
            strokes_given_to_team="",
            result=None,
            created_at=now,
            updated_at=now,
        )
        match2 = Match.reconstruct(
            id=match_id,
            round_id=RoundId.generate(),
            match_number=5,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
            status=MatchStatus.COMPLETED,
            handicap_strokes_given=10,
            strokes_given_to_team="A",
            result={"winner": "B"},
            created_at=now,
            updated_at=now,
        )

        assert match1 == match2

    def test_match_can_be_used_in_set(self):
        """Match puede usarse en set."""
        match = Match.create(
            round_id=RoundId.generate(),
            match_number=1,
            team_a_players=[create_match_player()],
            team_b_players=[create_match_player()],
        )

        match_set = {match}
        assert match in match_set
