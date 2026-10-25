"""
El resultado de un hoyo de match play de torneo con lo anotado (Agustin, 24
oct 2026): la raya pierde el hoyo, y en fourball se decide con las cuatro bolas
validadas. Antes un hoyo con raya se quedaba sin resultado.
"""

import pytest

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat

F = MatchFormat
RAYA = None
PARTIDO = MatchId.generate()


def _fila(team: str, golpes: int | None, *, recibe: int = 0, validada: bool = True) -> HoleScore:
    fila = HoleScore.create(
        match_id=PARTIDO,
        hole_number=1,
        player_user_id=UserId.generate(),
        team=team,
        strokes_received=recibe,
    )
    fila.set_own_score(golpes)
    if validada:
        fila.set_marker_score(golpes)
    fila.recalculate_validation()
    return fila


def _sin_anotar(team: str) -> HoleScore:
    return HoleScore.create(
        match_id=PARTIDO,
        hole_number=1,
        player_user_id=UserId.generate(),
        team=team,
        strokes_received=0,
    )


def _resultado(filas, formato=F.SINGLES):
    return ScoringService().hole_result(filas, formato)


class TestSingles:
    def test_t1_the_raya_gives_the_hole_to_the_rival(self):
        assert _resultado([_fila("A", RAYA), _fila("B", 9)]) == "B"
        assert _resultado([_fila("A", 9), _fila("B", RAYA)]) == "A"

    def test_t1_with_two_numbers_the_lower_net_wins(self):
        """5 recibiendo 1 es un 4 neto: gana al 5 sin golpes."""
        assert _resultado([_fila("A", 5, recibe=1), _fila("B", 5)]) == "A"
        assert _resultado([_fila("A", 5, recibe=1), _fila("B", 4)]) == "HALVED"

    def test_t2_both_pick_up_halved(self):
        assert _resultado([_fila("A", RAYA), _fila("B", RAYA)]) == "HALVED"

    @pytest.mark.parametrize("rival", ["sin anotar", "sin validar", "descuadre"])
    def test_t3_with_the_rival_not_validated_it_is_pending(self, rival):
        otro = {
            "sin anotar": _sin_anotar("B"),
            "sin validar": _fila("B", 4, validada=False),
            "descuadre": _fila("B", 4),
        }[rival]
        if rival == "descuadre":
            otro.set_marker_score(5)
            otro.recalculate_validation()

        assert _resultado([_fila("A", RAYA), otro]) is None


class TestFourball:
    def test_t4_the_partner_ball_counts_by_its_net(self):
        a = [_fila("A", RAYA), _fila("A", 5, recibe=1)]

        assert _resultado([*a, _fila("B", 4), _fila("B", 6)], F.FOURBALL) == "HALVED"
        assert _resultado([*a, _fila("B", 5), _fila("B", 6)], F.FOURBALL) == "A"
        assert _resultado([*a, _fila("B", 3), _fila("B", 6)], F.FOURBALL) == "B"

    def test_t5_both_pick_up_the_rival_wins(self):
        filas = [_fila("A", RAYA), _fila("A", RAYA), _fila("B", 9), _fila("B", RAYA)]

        assert _resultado(filas, F.FOURBALL) == "B"

    def test_t5_all_four_pick_up_halved(self):
        filas = [_fila("A", RAYA), _fila("A", RAYA), _fila("B", RAYA), _fila("B", RAYA)]

        assert _resultado(filas, F.FOURBALL) == "HALVED"

    def test_t6_it_waits_for_the_four_balls(self):
        """Hoy se decidia con una bola de cada bando: la que falta puede cambiarlo."""
        filas = [_fila("A", 4), _fila("A", 5), _fila("B", 5), _fila("B", 3, validada=False)]

        assert _resultado(filas, F.FOURBALL) is None

    def test_t6_a_raya_also_waits_for_the_four_balls(self):
        filas = [_fila("A", RAYA), _fila("A", RAYA), _fila("B", 9), _sin_anotar("B")]

        assert _resultado(filas, F.FOURBALL) is None


class TestFoursomes:
    def test_t7_the_side_that_picks_up_loses_the_hole(self):
        """La bola del bando se guarda en las dos filas del bando."""
        filas = [_fila("A", RAYA), _fila("A", RAYA), _fila("B", 8), _fila("B", 8)]

        assert _resultado(filas, F.FOURSOMES) == "B"

    def test_t7_one_validated_ball_per_side_is_enough(self):
        filas = [_fila("A", 4), _sin_anotar("A"), _fila("B", RAYA), _sin_anotar("B")]

        assert _resultado(filas, F.FOURSOMES) == "A"

    def test_t7_without_the_rival_ball_it_is_pending(self):
        filas = [_fila("A", RAYA), _fila("A", RAYA), _sin_anotar("B"), _sin_anotar("B")]

        assert _resultado(filas, F.FOURSOMES) is None


class TestConcededHole:
    def test_t8_a_conceded_hole_without_a_number_is_a_raya(self):
        """Conceder el hoyo es anotarlo sin numero: el marcador lo confirma igual."""
        concedido = _fila("A", RAYA)

        assert concedido.net_score is None
        assert _resultado([concedido, _fila("B", 7)]) == "B"


class TestWithoutARivalRow:
    def test_a_side_without_any_row_is_not_a_hole_won(self):
        assert _resultado([_fila("A", 4)]) is None
        assert _resultado([_fila("A", RAYA), _fila("A", 4)], F.FOURBALL) is None


class TestAMismatchedBall:
    def test_a_fourball_partner_in_mismatch_leaves_the_hole_open(self):
        descuadre = _fila("A", 4)
        descuadre.set_marker_score(5)
        descuadre.recalculate_validation()
        filas = [descuadre, _fila("A", 6), _fila("B", 5), _fila("B", 5)]

        assert _resultado(filas, F.FOURBALL) is None


class TestTheHolesOfTheMatch:
    def test_the_decided_holes_in_order_of_hole(self):
        def _en(hoyo, fila):
            fila._hole_number = hoyo
            return fila

        filas = [
            _en(3, _fila("A", 4)),
            _en(3, _fila("B", RAYA)),
            _en(1, _fila("A", RAYA)),
            _en(1, _fila("B", 5)),
            _en(2, _fila("A", 4)),
            _en(2, _fila("B", 4, validada=False)),
        ]

        assert ScoringService().hole_results(filas, F.SINGLES) == ["B", "A"]


class TestADisputedFoursomesBall:
    def test_a_side_row_in_mismatch_leaves_the_hole_open(self):
        """Las dos filas son la misma bola: si una esta en disputa, la bola tambien."""
        disputada = _fila("A", 4)
        disputada.set_marker_score(6)
        disputada.recalculate_validation()
        filas = [_fila("A", 4), disputada, _fila("B", 5), _fila("B", 5)]

        assert _resultado(filas, F.FOURSOMES) is None
