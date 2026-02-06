"""Tests para PlayingHandicapCalculator domain service."""

from decimal import Decimal

import pytest

from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode


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
        """Error si course_rating < 55."""
        with pytest.raises(ValueError, match="course_rating must be between"):
            TeeRating(course_rating=Decimal("54.0"), slope_rating=113, par=72)

    def test_course_rating_above_max_raises(self):
        """Error si course_rating > 85."""
        with pytest.raises(ValueError, match="course_rating must be between"):
            TeeRating(course_rating=Decimal("86.0"), slope_rating=113, par=72)

    def test_slope_rating_below_min_raises(self):
        """Error si slope_rating < 55."""
        with pytest.raises(ValueError, match="slope_rating must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=54, par=72)

    def test_slope_rating_above_max_raises(self):
        """Error si slope_rating > 155."""
        with pytest.raises(ValueError, match="slope_rating must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=156, par=72)

    def test_par_below_min_raises(self):
        """Error si par < 66."""
        with pytest.raises(ValueError, match="par must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=65)

    def test_par_above_max_raises(self):
        """Error si par > 76."""
        with pytest.raises(ValueError, match="par must be between"):
            TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=77)

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


class TestPlayingHandicapCalculatorSingles:
    """Tests para cálculo SINGLES"""

    def test_singles_match_play_uses_100_percent(self):
        """SINGLES MATCH_PLAY usa 100% allowance por defecto."""
        calculator = PlayingHandicapCalculator()
        player_tee = TeeRating(Decimal("72.0"), 120, 72)
        opponent_tee = TeeRating(Decimal("72.0"), 120, 72)

        player_ph, opponent_ph = calculator.calculate_for_singles(
            player_hi=Decimal("15.0"),
            player_tee=player_tee,
            opponent_hi=Decimal("10.0"),
            opponent_tee=opponent_tee,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

        # HI=15 con SR=120 → CH = 15×(120/113) + 0 = 15.93 → 16
        # HI=10 con SR=120 → CH = 10×(120/113) + 0 = 10.62 → 11
        assert player_ph == 16
        assert opponent_ph == 11

    def test_singles_custom_allowance_overrides_default(self):
        """Custom allowance reemplaza el default del modo."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        player_ph, opponent_ph = calculator.calculate_for_singles(
            player_hi=Decimal("20.0"),
            player_tee=tee,
            opponent_hi=Decimal("10.0"),
            opponent_tee=tee,
            handicap_mode=HandicapMode.MATCH_PLAY,
            custom_allowance=90,  # Override 100% default
        )

        # HI=20 × 90% = 18
        # HI=10 × 90% = 9
        assert player_ph == 18
        assert opponent_ph == 9


class TestPlayingHandicapCalculatorFourball:
    """Tests para cálculo FOURBALL"""

    def test_fourball_uses_90_percent_default(self):
        """FOURBALL usa 90% allowance por defecto."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        p1_ph, p2_ph = calculator.calculate_for_fourball(
            player1_hi=Decimal("20.0"),
            player1_tee=tee,
            player2_hi=Decimal("10.0"),
            player2_tee=tee,
        )

        # HI=20 × 90% = 18
        # HI=10 × 90% = 9
        assert p1_ph == 18
        assert p2_ph == 9

    def test_fourball_custom_allowance(self):
        """FOURBALL con allowance personalizado."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        p1_ph, p2_ph = calculator.calculate_for_fourball(
            player1_hi=Decimal("20.0"),
            player1_tee=tee,
            player2_hi=Decimal("10.0"),
            player2_tee=tee,
            custom_allowance=85,
        )

        # HI=20 × 85% = 17
        # HI=10 × 85% = 8.5 → 9
        assert p1_ph == 17
        assert p2_ph == 9


class TestPlayingHandicapCalculatorFoursomes:
    """Tests para cálculo FOURSOMES (golpe alterno)"""

    def test_foursomes_strokes_to_higher_handicap_team(self):
        """En FOURSOMES, el equipo con mayor CH recibe los strokes."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        # Team 1: avg HI = 15.0 → CH = 15
        # Team 2: avg HI = 10.0 → CH = 10
        # Diferencia = 5, 50% = 2.5 → 3 strokes
        team1_strokes, team2_strokes = calculator.calculate_for_foursomes(
            team1_hi_avg=Decimal("15.0"),
            team1_tee=tee,
            team2_hi_avg=Decimal("10.0"),
            team2_tee=tee,
        )

        assert team1_strokes == 3  # Team 1 (mayor CH) recibe strokes
        assert team2_strokes == 0

    def test_foursomes_lower_handicap_team_receives_zero(self):
        """El equipo con menor CH no recibe strokes."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        # Team 1: avg HI = 5.0 → CH = 5
        # Team 2: avg HI = 20.0 → CH = 20
        # Diferencia = 15, 50% = 7.5 → 8 strokes para Team 2
        team1_strokes, team2_strokes = calculator.calculate_for_foursomes(
            team1_hi_avg=Decimal("5.0"),
            team1_tee=tee,
            team2_hi_avg=Decimal("20.0"),
            team2_tee=tee,
        )

        assert team1_strokes == 0  # Team 1 (menor CH) no recibe nada
        assert team2_strokes == 8

    def test_foursomes_equal_handicaps_zero_strokes(self):
        """Con handicaps iguales, nadie recibe strokes."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        team1_strokes, team2_strokes = calculator.calculate_for_foursomes(
            team1_hi_avg=Decimal("12.0"),
            team1_tee=tee,
            team2_hi_avg=Decimal("12.0"),
            team2_tee=tee,
        )

        assert team1_strokes == 0
        assert team2_strokes == 0

    def test_foursomes_custom_allowance(self):
        """FOURSOMES con allowance personalizado."""
        calculator = PlayingHandicapCalculator()
        tee = TeeRating(Decimal("72.0"), 113, 72)

        # Diferencia = 10, con 60% = 6 strokes
        team1_strokes, team2_strokes = calculator.calculate_for_foursomes(
            team1_hi_avg=Decimal("20.0"),
            team1_tee=tee,
            team2_hi_avg=Decimal("10.0"),
            team2_tee=tee,
            custom_allowance=60,
        )

        assert team1_strokes == 6
        assert team2_strokes == 0


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
        ph_a, ph_b = calculator.calculate_for_singles(
            player_hi=Decimal("8.2"),
            player_tee=tee,
            opponent_hi=Decimal("14.5"),
            opponent_tee=tee,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

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
        ph_man, ph_woman = calculator.calculate_for_singles(
            player_hi=Decimal("10.0"),
            player_tee=championship,
            opponent_hi=Decimal("18.0"),
            opponent_tee=regular,
            handicap_mode=HandicapMode.MATCH_PLAY,
        )

        # Hombre: 10 × (135/113) + (73-72) = 11.95 + 1 = 12.95 → 13
        # Mujer: 18 × (115/113) + (69.5-72) = 18.31 - 2.5 = 15.81 → 16
        assert ph_man == 13
        assert ph_woman == 16
