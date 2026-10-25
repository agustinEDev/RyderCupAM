"""
Las reglas del match play (RyderCupAM#165).

Ganador de cada hoyo, cómo va el partido, si está decidido y el resultado tipo
4&2. Estaban en el ScoringService de competición, y las usan también la
partida rápida y las estadísticas: ahora viven en shared, y ScoringService las
hereda y añade lo de la Ryder (marcadores y puntos).
"""

import pytest

from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.value_objects.match_format import MatchFormat


@pytest.fixture
def service():
    return MatchPlayScoring()


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


# ==================== Decidido en el orden de los hoyos ====================


# El caso del revisor del Kind (24 oct 2026): gana A el 1, 2, 3, 6 y 7, el 4 y
# el 5 son de B y del 8 en adelante se empatan. En orden queda decidido en el
# 16, «3&2». Contando sin orden, con el 4 y el 5 aun abiertos, salia «5&4».
REVISOR = {
    **dict.fromkeys((1, 2, 3, 6, 7), "A"),
    **dict.fromkeys(range(8, 18), "HALVED"),
}


class TestDecidedInHoleOrder:
    """
    El partido se decide en el primer hoyo en que la ventaja supera a los que
    quedan, con todos los anteriores cerrados (Agustin, 25 oct 2026).
    """

    def test_d1_holes_closed_in_order_decided_on_the_16th(self, service):
        resultados = {**REVISOR, 4: "B", 5: "B"}
        assert service.decided_in_hole_order(resultados) == {"winner": "A", "score": "3&2"}

    def test_d2_with_the_4th_and_5th_open_it_is_still_in_play(self, service):
        assert service.decided_in_hole_order(REVISOR) is None

    def test_d3_once_the_gap_closes_the_score_follows_the_order_of_play(self, service):
        resultados = {**REVISOR, 5: "B", 4: "B"}
        assert service.decided_in_hole_order(resultados) == {"winner": "A", "score": "3&2"}

    def test_d4_a_gap_after_the_decision_does_not_count(self, service):
        resultados = {**dict.fromkeys(range(1, 12), "A"), 13: "B", 14: "B"}
        assert service.decided_in_hole_order(resultados) == {"winner": "A", "score": "10&8"}

    def test_d5_won_on_the_18th_by_one_hole(self, service):
        resultados = {1: "B", **dict.fromkeys(range(2, 19), "HALVED")}
        assert service.decided_in_hole_order(resultados) == {"winner": "B", "score": "1UP"}

    def test_d5_all_square_on_the_18th_is_not_decided(self, service):
        assert service.decided_in_hole_order(dict.fromkeys(range(1, 19), "HALVED")) is None

    def test_d5_one_up_with_a_hole_left_is_not_decided(self, service):
        resultados = {1: "A", **dict.fromkeys(range(2, 18), "HALVED")}
        assert service.decided_in_hole_order(resultados) is None

    def test_without_the_first_hole_nothing_is_decided(self, service):
        assert service.decided_in_hole_order(dict.fromkeys(range(2, 19), "A")) is None

    def test_without_holes_nothing_is_decided(self, service):
        assert service.decided_in_hole_order({}) is None


# ==================== Ryder Cup Points ====================
