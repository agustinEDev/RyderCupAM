"""
Tests del ScoreDifferentialCalculator (BE #167).

El diferencial es la única métrica de la app que pretende ser WHS de verdad, así
que estos tests fijan sobre todo dos cosas: que la fórmula da los números del
sistema y que la tabla de la Regla 5.2 se aplica escalón a escalón. El resto de
métricas de jugador son de la casa y pueden cambiar; esta no.
"""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.competition.domain.services.score_differential_calculator import (
    PlayedRound,
    ScoreDifferentialCalculator,
)


def _round(adjusted_gross_score: int, slope: int = 113, course_rating: str = "72.0") -> PlayedRound:
    """Una vuelta desde un tee cualquiera; por defecto, slope neutro."""
    return PlayedRound(
        adjusted_gross_score=adjusted_gross_score,
        tee_rating=TeeRating(
            course_rating=Decimal(course_rating), slope_rating=slope, par=72
        ),
    )


def _differentials(values: list[str]) -> list[Decimal]:
    return [Decimal(value) for value in values]


class TestDifferential:
    """`(113 / Slope) x (AGS - CR)`."""

    def test_slope_neutral_leaves_the_margin_over_the_rating_untouched(self):
        # 85 golpes en un campo de rating 72 y slope 113: se jugó 13 sobre
        assert ScoreDifferentialCalculator.differential(_round(85)) == Decimal("13.0")

    def test_playing_to_the_rating_is_a_scratch_round(self):
        assert ScoreDifferentialCalculator.differential(_round(72)) == Decimal("0.0")

    def test_beating_the_rating_gives_a_plus_differential(self):
        assert ScoreDifferentialCalculator.differential(_round(70)) == Decimal("-2.0")

    def test_a_hard_course_shrinks_the_differential(self):
        # Mismos 85 golpes, pero desde un tee más difícil: la vuelta vale más
        assert ScoreDifferentialCalculator.differential(
            _round(85, slope=140)
        ) == Decimal("10.5")

    def test_an_easy_course_stretches_the_differential(self):
        assert ScoreDifferentialCalculator.differential(
            _round(85, slope=100)
        ) == Decimal("14.7")

    def test_the_rating_decimals_carry_into_the_result(self):
        # 85 - 71.4 = 13.6, en slope neutro
        assert ScoreDifferentialCalculator.differential(
            _round(85, course_rating="71.4")
        ) == Decimal("13.6")

    def test_rounds_to_one_decimal(self):
        # (113/128) x (85 - 72.3) = 11.212...
        assert ScoreDifferentialCalculator.differential(
            _round(85, slope=128, course_rating="72.3")
        ) == Decimal("11.2")

    def test_keeps_the_order_of_the_rounds_it_receives(self):
        result = ScoreDifferentialCalculator.differentials([_round(85), _round(72)])
        assert result == [Decimal("13.0"), Decimal("0.0")]


class TestEstimatedIndex:
    """Tabla de la Regla WHS 5.2: cuántas vueltas se promedian y con qué ajuste."""

    def test_no_index_without_rounds(self):
        assert ScoreDifferentialCalculator.estimated_index([]) is None

    @pytest.mark.parametrize("count", [1, 2])
    def test_no_index_below_three_rounds(self, count):
        assert ScoreDifferentialCalculator.estimated_index(_differentials(["10.0"] * count)) is None

    def test_three_rounds_take_the_best_one_minus_two(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["18.0", "12.0", "15.0"])
        )
        assert result == Decimal("10.0")

    def test_four_rounds_take_the_best_one_minus_one(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["18.0", "12.0", "15.0", "20.0"])
        )
        assert result == Decimal("11.0")

    def test_five_rounds_take_the_best_one_with_no_adjustment(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["18.0", "12.0", "15.0", "20.0", "17.0"])
        )
        assert result == Decimal("12.0")

    def test_six_rounds_average_the_two_best_minus_one(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["18.0", "12.0", "15.0", "20.0", "17.0", "14.0"])
        )
        # (12.0 + 14.0) / 2 - 1.0
        assert result == Decimal("12.0")

    def test_seven_rounds_average_the_two_best_with_no_adjustment(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["18.0", "12.0", "15.0", "20.0", "17.0", "14.0", "19.0"])
        )
        assert result == Decimal("13.0")

    def test_twenty_rounds_average_the_eight_best(self):
        # 1.0 .. 20.0: los ocho mejores son 1..8, media 4.5
        differentials = _differentials([f"{value}.0" for value in range(1, 21)])
        assert ScoreDifferentialCalculator.estimated_index(differentials) == Decimal("4.5")

    def test_only_the_twenty_most_recent_rounds_count(self):
        # Una vuelta excelente muy antigua queda fuera de la ventana
        differentials = _differentials([f"{value}.0" for value in range(10, 30)])
        differentials.append(Decimal("0.5"))
        assert ScoreDifferentialCalculator.estimated_index(differentials) == Decimal("13.5")

    def test_rounds_the_index_to_one_decimal(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["10.1", "10.2", "10.4"])
        )
        # mejor 10.1 - 2.0
        assert result == Decimal("8.1")

    def test_a_plus_player_gets_a_negative_index(self):
        result = ScoreDifferentialCalculator.estimated_index(
            _differentials(["-1.0", "0.5", "1.0"])
        )
        assert result == Decimal("-3.0")


class TestPlayingAverage:
    """La media de todas las vueltas recientes, no solo de las buenas."""

    def test_no_average_without_rounds(self):
        assert ScoreDifferentialCalculator.playing_average([]) is None

    def test_a_single_round_is_its_own_average(self):
        assert ScoreDifferentialCalculator.playing_average(_differentials(["13.0"])) == Decimal(
            "13.0"
        )

    def test_averages_the_good_and_the_bad_alike(self):
        result = ScoreDifferentialCalculator.playing_average(
            _differentials(["10.0", "20.0", "15.0"])
        )
        assert result == Decimal("15.0")

    def test_is_worse_than_the_index_over_the_same_rounds(self):
        differentials = _differentials(["12.0", "18.0", "20.0", "14.0", "22.0"])
        index = ScoreDifferentialCalculator.estimated_index(differentials)
        average = ScoreDifferentialCalculator.playing_average(differentials)
        assert average > index

    def test_only_the_twenty_most_recent_rounds_count(self):
        differentials = _differentials(["10.0"] * 20 + ["100.0"])
        assert ScoreDifferentialCalculator.playing_average(differentials) == Decimal("10.0")


class TestBestDifferential:
    """La mejor vuelta del registro."""

    def test_no_best_without_rounds(self):
        assert ScoreDifferentialCalculator.best_differential([]) is None

    def test_takes_the_lowest_differential(self):
        result = ScoreDifferentialCalculator.best_differential(
            _differentials(["13.0", "8.5", "11.0"])
        )
        assert result == Decimal("8.5")

    def test_ignores_rounds_outside_the_window(self):
        differentials = _differentials(["10.0"] * 20 + ["1.0"])
        assert ScoreDifferentialCalculator.best_differential(differentials) == Decimal("10.0")


class TestTrend:
    """Vueltas recientes contra las anteriores. Negativo es mejorar."""

    @pytest.mark.parametrize("count", [0, 5, 9])
    def test_no_trend_without_two_full_windows(self, count):
        assert ScoreDifferentialCalculator.trend(_differentials(["10.0"] * count)) is None

    def test_improving_gives_a_negative_trend(self):
        # Cinco vueltas recientes a 10, cinco anteriores a 14
        differentials = _differentials(["10.0"] * 5 + ["14.0"] * 5)
        assert ScoreDifferentialCalculator.trend(differentials) == Decimal("-4.0")

    def test_getting_worse_gives_a_positive_trend(self):
        differentials = _differentials(["16.0"] * 5 + ["12.0"] * 5)
        assert ScoreDifferentialCalculator.trend(differentials) == Decimal("4.0")

    def test_steady_play_gives_no_change(self):
        assert ScoreDifferentialCalculator.trend(_differentials(["13.0"] * 10)) == Decimal("0.0")

    def test_ignores_anything_older_than_the_two_windows(self):
        differentials = _differentials(["10.0"] * 5 + ["14.0"] * 5 + ["99.0"] * 10)
        assert ScoreDifferentialCalculator.trend(differentials) == Decimal("-4.0")

    def test_rounds_the_change_to_one_decimal(self):
        differentials = _differentials(["10.0"] * 5 + ["10.5", "10.0", "10.0", "10.0", "10.0"])
        # 0.5 repartido entre 5 vueltas
        assert ScoreDifferentialCalculator.trend(differentials) == Decimal("-0.1")
