"""Tests para PlayingHandicapCalculator domain service."""

from decimal import Decimal
from typing import ClassVar

import pytest

from src.shared.domain.services.playing_handicap_calculator import (
    ALLOWED_ALLOWANCE_PERCENTAGES,
    PlayingHandicapCalculator,
    TeeRating,
    round_half_up,
)
from src.shared.domain.value_objects.match_format import MatchFormat


class TestTeeRating:
    """Tests para TeeRating dataclass"""

    def test_create_valid_tee_rating(self):
        """Crea TeeRating con valores válidos."""
        rating = TeeRating(
            course_rating=Decimal("71.2"),
            slope_rating=128,
            par=72,
        )

        assert rating.course_rating == Decimal("71.2")
        assert rating.slope_rating == 128
        assert rating.par == 72

    def test_course_rating_below_min_raises(self):
        """Error si course_rating < 45."""
        with pytest.raises(ValueError, match="course_rating must be between"):
            TeeRating(course_rating=Decimal("44.0"), slope_rating=113, par=72)

    def test_course_rating_above_max_raises(self):
        """Error si course_rating > 90."""
        with pytest.raises(ValueError, match="course_rating must be between"):
            TeeRating(course_rating=Decimal("91.0"), slope_rating=113, par=72)

    def test_slope_rating_below_min_raises(self):
        """Error si slope_rating < 40."""
        with pytest.raises(ValueError, match="slope_rating must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=39, par=72)

    def test_slope_rating_above_max_raises(self):
        """Error si slope_rating > 160."""
        with pytest.raises(ValueError, match="slope_rating must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=161, par=72)

    def test_par_below_min_raises(self):
        """Error si par < 50."""
        with pytest.raises(ValueError, match="par must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=49)

    def test_par_above_max_raises(self):
        """Error si par > 80."""
        with pytest.raises(ValueError, match="par must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=81)

    def test_admite_un_pitch_and_putt_federado(self):
        """
        Los rangos son la union de todos los tipos de campo, no los de un 18
        hoyos: con los de antes (CR 55-85, par 66-76) un pitch & putt federado
        no se podia valorar, y sus jugadores acababan jugando con el Handicap
        Index a pelo —o, en competicion, sin poder generar los partidos—.
        Datos reales de Son Parc naranjas. Ver RyderCupAm#206 y RyderCupAm#219.
        """
        rating = TeeRating(course_rating=Decimal("54.9"), slope_rating=91, par=58)

        assert rating.course_rating == Decimal("54.9")
        assert rating.par == 58

    def test_admite_los_extremos_del_catalogo_federado(self):
        """El catalogo va de CR 46.5 a 84.7 y de SR 46 a 157: todo debe entrar."""
        TeeRating(course_rating=Decimal("46.5"), slope_rating=46, par=54)
        TeeRating(course_rating=Decimal("84.7"), slope_rating=157, par=74)

    def test_tee_rating_is_frozen(self):
        """TeeRating es inmutable."""
        rating = TeeRating(
            course_rating=Decimal("71.2"),
            slope_rating=128,
            par=72,
        )

        with pytest.raises(AttributeError):
            rating.slope_rating = 130


class TestPlayingHandicapCalculatorBasic:
    """Tests básicos para PlayingHandicapCalculator"""

    def test_calculate_with_neutral_slope(self):
        """Cálculo con slope neutral (113) es directo."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(
            course_rating=Decimal("72.0"),
            slope_rating=113,  # Neutral slope
            par=72,
        )

        # HI=12.0, SR=113 → CH = 12.0 × 1.0 + 0 = 12.0
        # Con 100% allowance → PH = 12
        result = calculator.calculate(
            handicap_index=Decimal("12.0"),
            tee_rating=tee,
            allowance_percentage=100,
        )

        assert result == 12

    def test_calculate_with_high_slope(self):
        """Slope alto aumenta el Playing Handicap."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(
            course_rating=Decimal("73.5"),
            slope_rating=135,
            par=72,
        )

        # HI=10.0, SR=135 → CH = 10.0 × (135/113) + (73.5-72)
        # = 10.0 × 1.195 + 1.5 = 11.95 + 1.5 = 13.45
        # Con 100% allowance → 13 (redondeado)
        result = calculator.calculate(
            handicap_index=Decimal("10.0"),
            tee_rating=tee,
            allowance_percentage=100,
        )

        assert result == 13

    def test_calculate_with_allowance_95(self):
        """95% allowance reduce el Playing Handicap."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(
            course_rating=Decimal("72.0"),
            slope_rating=113,
            par=72,
        )

        # HI=20.0, CH = 20.0, PH = 20.0 × 0.95 = 19
        result = calculator.calculate(
            handicap_index=Decimal("20.0"),
            tee_rating=tee,
            allowance_percentage=95,
        )

        assert result == 19

    def test_calculate_rounding_half_up(self):
        """0.5 redondea hacia arriba."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(
            course_rating=Decimal("72.0"),
            slope_rating=113,
            par=72,
        )

        # HI=10.5 → CH = 10.5, con 100% → 10.5 redondea a 11
        result = calculator.calculate(
            handicap_index=Decimal("10.5"),
            tee_rating=tee,
            allowance_percentage=100,
        )

        assert result == 11

    def test_calculate_minimum_zero(self):
        """Playing Handicap nunca es negativo."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(
            course_rating=Decimal("68.0"),  # Fácil
            slope_rating=100,
            par=72,
        )

        # HI=1.0, CR-Par=-4 → CH = 1×(100/113) + (-4) ≈ -3.1
        # Con 100% allowance → 0 (mínimo)
        result = calculator.calculate(
            handicap_index=Decimal("1.0"),
            tee_rating=tee,
            allowance_percentage=100,
        )

        assert result == 0


class TestPlayingHandicapCalculatorSinglesDifferential:
    """Tests para calculate_singles_differential (método diferencial WHS Match Play)."""

    HOLES_BY_STROKE_INDEX: ClassVar[list[int]] = list(range(1, 19))  # hoyo 1 = mas dificil (SI 1)

    def test_higher_ph_player_receives_strokes(self):
        strokes_a, strokes_b = PlayingHandicapCalculator.calculate_singles_differential(
            ph_a=16, ph_b=11, holes_by_stroke_index=self.HOLES_BY_STROKE_INDEX
        )

        assert strokes_a == [1, 2, 3, 4, 5]
        assert strokes_b == []

    def test_lower_ph_player_plays_off_scratch(self):
        strokes_a, strokes_b = PlayingHandicapCalculator.calculate_singles_differential(
            ph_a=11, ph_b=16, holes_by_stroke_index=self.HOLES_BY_STROKE_INDEX
        )

        assert strokes_a == []
        assert strokes_b == [1, 2, 3, 4, 5]

    def test_equal_ph_nobody_receives_strokes(self):
        strokes_a, strokes_b = PlayingHandicapCalculator.calculate_singles_differential(
            ph_a=12, ph_b=12, holes_by_stroke_index=self.HOLES_BY_STROKE_INDEX
        )

        assert strokes_a == []
        assert strokes_b == []

    def test_diff_over_18_wraps_around_hardest_holes(self):
        strokes_a, strokes_b = PlayingHandicapCalculator.calculate_singles_differential(
            ph_a=20, ph_b=0, holes_by_stroke_index=self.HOLES_BY_STROKE_INDEX
        )

        assert len(strokes_a) == 20
        assert strokes_a.count(1) == 2  # hoyo mas dificil recibe 2 golpes
        assert strokes_a.count(18) == 1
        assert strokes_b == []


class TestPlayingHandicapCalculatorRealScenarios:
    """Tests con escenarios reales de golf"""

    def test_real_scenario_valderrama(self):
        """Escenario real: Valderrama Championship tees."""
        calculator = PlayingHandicapCalculator()

        # Valderrama Championship: CR=74.2, SR=143, Par=71
        valderrama = TeeRating(
            course_rating=Decimal("74.2"),
            slope_rating=143,
            par=71,
        )

        # Jugador con HI=12.4
        # CH = 12.4 × (143/113) + (74.2-71) = 12.4 × 1.265 + 3.2 = 15.69 + 3.2 = 18.89
        # Con 100% → 19
        result = calculator.calculate(
            handicap_index=Decimal("12.4"),
            tee_rating=valderrama,
            allowance_percentage=100,
        )

        assert result == 19

    def test_real_scenario_match_play_tournament(self):
        """Torneo Match Play estilo Ryder Cup."""
        calculator = PlayingHandicapCalculator()

        # Campo estándar
        tee = TeeRating(Decimal("72.5"), 128, 72)

        # Jugador A (HI=8.2) vs Jugador B (HI=14.5)
        # Singles: cada uno al 100% (MatchFormat.SINGLES.default_allowance)
        ph_a = calculator.calculate(Decimal("8.2"), tee, 100)
        ph_b = calculator.calculate(Decimal("14.5"), tee, 100)

        # A: 8.2 × (128/113) + 0.5 = 9.29 + 0.5 = 9.79 → 10
        # B: 14.5 × (128/113) + 0.5 = 16.42 + 0.5 = 16.92 → 17
        # Diferencia: 7 strokes a favor de B
        assert ph_a == 10
        assert ph_b == 17
        assert ph_b - ph_a == 7

    def test_real_scenario_different_tees(self):
        """Jugadores desde diferentes tees."""
        calculator = PlayingHandicapCalculator()

        # Championship tees (hombre)
        championship = TeeRating(Decimal("73.0"), 135, 72)

        # Regular tees (senior/mujer)
        regular = TeeRating(Decimal("69.5"), 115, 72)

        # Hombre HI=10 desde championship
        # Mujer HI=18 desde regular
        ph_man = calculator.calculate(Decimal("10.0"), championship, 100)
        ph_woman = calculator.calculate(Decimal("18.0"), regular, 100)

        # Hombre: 10 × (135/113) + (73-72) = 11.95 + 1 = 12.95 → 13
        # Mujer: 18 × (115/113) + (69.5-72) = 18.31 - 2.5 = 15.81 → 16
        assert ph_man == 13
        assert ph_woman == 16


class TestPlayingHandicapCalculatorMaxHandicap:
    """Tests para el límite máximo de hándicap de juego (max_playing_handicap)."""

    def test_calculate_caps_result_when_above_limit(self):
        """El resultado queda limitado al cap cuando supera max_playing_handicap."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        # HI=36.0 con slope neutro y 100% → PH = 36
        # Cap de 18 → resultado debe ser 18
        result = calculator.calculate(
            handicap_index=Decimal("36.0"),
            tee_rating=tee,
            allowance_percentage=100,
            max_playing_handicap=18,
        )

        assert result == 18

    def test_calculate_no_cap_applied_when_below_limit(self):
        """El resultado no se altera cuando el PH calculado está por debajo del límite."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        result = calculator.calculate(
            handicap_index=Decimal("10.0"),
            tee_rating=tee,
            allowance_percentage=100,
            max_playing_handicap=18,
        )

        assert result == 10

    def test_calculate_no_cap_when_none(self):
        """Sin cap (None), el resultado puede superar cualquier límite."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        result = calculator.calculate(
            handicap_index=Decimal("54.0"),
            tee_rating=tee,
            allowance_percentage=100,
            max_playing_handicap=None,
        )

        assert result == 54

    def test_calculate_cap_exactly_at_limit(self):
        """El resultado es igual al cap cuando el PH calculado coincide exactamente."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        result = calculator.calculate(
            handicap_index=Decimal("20.0"),
            tee_rating=tee,
            allowance_percentage=100,
            max_playing_handicap=20,
        )

        assert result == 20

    def test_calculate_cap_applied_with_allowance(self):
        """El cap se aplica DESPUÉS del allowance, no antes."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        # HI=36.0, 50% allowance → PH = 18, cap=10 → resultado=10
        result = calculator.calculate(
            handicap_index=Decimal("36.0"),
            tee_rating=tee,
            allowance_percentage=50,
            max_playing_handicap=10,
        )

        assert result == 10

    def test_calculate_cap_not_needed_with_allowance(self):
        """Con allowance bajo, el PH puede quedar ya por debajo del cap."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        # HI=36.0, 50% allowance → PH = 18, cap=20 → resultado=18 (no se aplica)
        result = calculator.calculate(
            handicap_index=Decimal("36.0"),
            tee_rating=tee,
            allowance_percentage=50,
            max_playing_handicap=20,
        )

        assert result == 18

    def test_fourball_differential_caps_result_when_above_limit(self):
        """calculate_fourball_differential aplica el mismo cap que calculate()."""
        result = PlayingHandicapCalculator.calculate_fourball_differential(
            player_course_handicaps=[("p1", 10), ("p2", 30)],
            allowance_percentage=100,
            max_playing_handicap=15,
        )

        # p1: diff=0 → ph=0 (sin cap). p2: diff=20 → ph=20 → acotado a 15
        assert result["p1"] == 0
        assert result["p2"] == 15

    def test_fourball_differential_no_cap_when_none(self):
        """Sin cap (None), calculate_fourball_differential no acota el resultado."""
        result = PlayingHandicapCalculator.calculate_fourball_differential(
            player_course_handicaps=[("p1", 10), ("p2", 30)],
            allowance_percentage=100,
            max_playing_handicap=None,
        )

        assert result["p2"] == 20

    def test_foursomes_differential_caps_result_when_above_limit(self):
        """calculate_foursomes_differential aplica el mismo cap que calculate()."""
        team_a_ph, team_b_ph = PlayingHandicapCalculator.calculate_foursomes_differential(
            team_a_course_handicaps=[10, 10],
            team_b_course_handicaps=[30, 30],
            allowance_percentage=100,
            max_playing_handicap=15,
        )

        # Equipo B tiene mayor CH promedio: diff=20 → 20 strokes → acotado a 15
        assert team_a_ph == 0
        assert team_b_ph == 15

    def test_foursomes_differential_no_cap_when_none(self):
        """Sin cap (None), calculate_foursomes_differential no acota el resultado."""
        _team_a_ph, team_b_ph = PlayingHandicapCalculator.calculate_foursomes_differential(
            team_a_course_handicaps=[10, 10],
            team_b_course_handicaps=[30, 30],
            allowance_percentage=100,
            max_playing_handicap=None,
        )

        assert team_b_ph == 20


class TestAllowedAllowancePercentages:
    """
    Los porcentajes que se pueden elegir a mano (RyderCupAM#165).

    Estaban dos veces, en `Round` (ALLOWED_PERCENTAGES) y en `QuickMatch`
    (ALLOWED_ALLOWANCE_PERCENTAGES): ahora viven con el cálculo.
    """

    def test_de_50_a_100_de_5_en_5(self):
        assert sorted(ALLOWED_ALLOWANCE_PERCENTAGES) == list(range(50, 101, 5))

    def test_los_porcentajes_por_defecto_estan_entre_los_permitidos(self):
        """Si no, una ronda sin porcentaje propio no se podría editar con el suyo."""
        for formato in MatchFormat:
            assert formato.default_allowance in ALLOWED_ALLOWANCE_PERCENTAGES


class TestRoundHalfUp:
    """
    El redondeo de todo el cálculo de hándicap (RyderCupAM#165).

    Estaba copiado cinco veces: cuatro dentro del calculador y una en la partida
    rápida. Redondea alejándose del cero, como el frontend. `round()` de Python y
    `Decimal.to_integral_value()` redondean al par en los .5, y los hándicaps
    acabados en .5 son de lo más común.
    """

    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [
            ("20.5", 21),
            ("21.5", 22),
            ("2.4", 2),
            ("2.6", 3),
            ("-2.5", -3),
            ("-2.4", -2),
            ("0", 0),
        ],
    )
    def test_se_aleja_del_cero_en_los_medios(self, valor, esperado):
        assert round_half_up(Decimal(valor)) == esperado
