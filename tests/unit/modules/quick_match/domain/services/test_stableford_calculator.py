"""
Tests del StablefordCalculator (BE #128).

Estas reglas vivían solo en el frontend (`StablefordCalculator.js`) y ahora
existen por duplicado. Mientras las dos implementaciones coexistan, el riesgo
real es que se separen sin que nadie se entere, así que buena parte de estos
tests fija la paridad: mismos datos, mismos números que el frontend produce hoy.
"""

from decimal import Decimal
from typing import ClassVar

import pytest

from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.quick_match.domain.services.stableford_calculator import (
    HoleSetup,
    StablefordCalculator,
)


def _course(pars: list[int] | None = None) -> list[HoleSetup]:
    """18 hoyos con stroke index 1..18 en orden."""
    pars = pars or [4] * 18
    return [
        HoleSetup(hole_number=i + 1, par=pars[i], stroke_index=i + 1) for i in range(18)
    ]


class TestAllocateStrokes:
    """Reparto de golpes por hoyo."""

    def test_no_handicap_receives_no_strokes(self):
        assert StablefordCalculator.allocate_strokes(None, 1) == 0

    def test_scratch_receives_no_strokes(self):
        assert StablefordCalculator.allocate_strokes(Decimal("0"), 1) == 0

    @pytest.mark.parametrize(
        ("handicap", "stroke_index", "expected"),
        [
            (Decimal("10"), 1, 1),  # entra en los 10 hoyos más difíciles
            (Decimal("10"), 10, 1),  # justo el último que recibe
            (Decimal("10"), 11, 0),  # ya no
            (Decimal("18"), 18, 1),  # uno en cada hoyo
            (Decimal("20"), 1, 2),  # vuelta completa más dos
            (Decimal("20"), 2, 2),
            (Decimal("20"), 3, 1),
            (Decimal("36"), 18, 2),  # dos vueltas exactas
        ],
    )
    def test_allocates_by_difficulty(self, handicap, stroke_index, expected):
        assert StablefordCalculator.allocate_strokes(handicap, stroke_index) == expected

    @pytest.mark.parametrize(
        ("handicap", "stroke_index", "expected"),
        [
            (Decimal("-2"), 18, -1),  # el plus cede en el hoyo más fácil
            (Decimal("-2"), 17, -1),
            (Decimal("-2"), 16, 0),  # y no en el resto
            (Decimal("-1"), 18, -1),
            (Decimal("-1"), 17, 0),
        ],
    )
    def test_plus_handicap_gives_strokes_from_the_easiest_hole(
        self, handicap, stroke_index, expected
    ):
        """Regla WHS 8.2: al plus se le quitan golpes empezando por el más fácil."""
        assert StablefordCalculator.allocate_strokes(handicap, stroke_index) == expected

    @pytest.mark.parametrize(
        ("handicap", "expected_rounded_effect"),
        [
            (Decimal("2.5"), 1),  # Math.round(2.5) = 3 -> recibe en SI 1
            (Decimal("-2.5"), 0),  # Math.round(-2.5) = -2 -> no cede en SI 1
        ],
    )
    def test_rounds_the_half_the_same_way_the_frontend_does(
        self, handicap, expected_rounded_effect
    ):
        """
        El frontend usa Math.round, que manda el medio hacia arriba también en
        negativos. ROUND_HALF_UP de Decimal se aleja del cero y daría otro
        resultado para -2.5, con un golpe de diferencia.
        """
        assert (
            StablefordCalculator.allocate_strokes(handicap, 1) == expected_rounded_effect
        )


class TestHolePoints:
    """Puntos de un hoyo."""

    @pytest.mark.parametrize(
        ("gross", "par", "strokes", "expected"),
        [
            (4, 4, 0, 2),  # par
            (3, 4, 0, 3),  # birdie
            (2, 4, 0, 4),  # eagle
            (5, 4, 0, 1),  # bogey
            (6, 4, 0, 0),  # doble
            (7, 4, 0, 0),  # nunca negativo
            (5, 4, 1, 2),  # bogey bruto con golpe = par neto
            (6, 4, 2, 2),
        ],
    )
    def test_points_follow_net_score_against_par(self, gross, par, strokes, expected):
        assert StablefordCalculator.hole_points(gross, par, strokes) == expected

    def test_hole_without_score_gives_no_points(self):
        assert StablefordCalculator.hole_points(None, 4, 0) == 0


class TestComputeParticipantTotals:
    """Agregación sobre la vuelta."""

    def test_only_counts_holes_with_a_score(self):
        """Una partida a medias puntúa por lo jugado, no por lo que falta."""
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: 4, 2: 4, 3: 4}
        )

        assert totals.holes_played == 3
        assert totals.total_strokes == 12
        assert totals.par_played == 12
        assert totals.stableford_points == 6

    def test_scratch_round_at_par(self):
        calculator = StablefordCalculator()
        scores = dict.fromkeys(range(1, 19), 4)

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole=scores
        )

        assert totals.stableford_points == 36
        assert totals.to_par == 0
        assert calculator.format_to_par(totals.to_par) == "PAR"

    def test_handicap_player_gets_net_credit(self):
        """18 de hándicap: un golpe por hoyo, así que 5 brutos son par neto."""
        calculator = StablefordCalculator()
        scores = dict.fromkeys(range(1, 19), 5)

        totals = calculator.compute_participant_totals(
            handicap=18, holes=_course(), scores_by_hole=scores
        )

        assert totals.stableford_points == 36
        assert totals.total_strokes == 90
        assert totals.net_strokes == 72
        assert totals.to_par == 0

    def test_participant_without_handicap_gets_no_strokes(self):
        calculator = StablefordCalculator()
        scores = dict.fromkeys(range(1, 19), 5)

        totals = calculator.compute_participant_totals(
            handicap=None, holes=_course(), scores_by_hole=scores
        )

        assert totals.net_strokes == totals.total_strokes
        assert totals.stableford_points == 18  # bogey en todos: 1 punto por hoyo

    def test_no_scores_at_all_is_an_empty_round_not_an_error(self):
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=10, holes=_course(), scores_by_hole={}
        )

        assert totals.holes_played == 0
        assert totals.stableford_points == 0
        assert totals.to_par == 0


class TestNetDoubleBogeyCap:
    """Regla WHS 3.1: lo que puntúa para hándicap tiene techo por hoyo."""

    def test_a_normal_hole_is_left_alone(self):
        assert StablefordCalculator.adjusted_gross(5, par=4, strokes_received=0) == 5

    def test_a_disaster_hole_is_capped_at_net_double_bogey(self):
        """Un 11 en un par 4 sin golpes cuenta como 6, no como 11."""
        assert StablefordCalculator.adjusted_gross(11, par=4, strokes_received=0) == 6

    def test_the_cap_rises_with_the_strokes_received(self):
        """Con dos golpes en el hoyo, el techo sube a par + 2 + 2."""
        assert StablefordCalculator.adjusted_gross(11, par=4, strokes_received=2) == 8

    def test_the_cap_is_off_by_default_so_the_scorecard_shows_real_strokes(self):
        calculator = StablefordCalculator()
        scores = {**dict.fromkeys(range(1, 18), 4), 18: 11}

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole=scores
        )

        assert totals.total_strokes == 79
        assert totals.to_par == 7

    def test_the_cap_limits_what_a_single_hole_can_do_to_the_average(self):
        """Los mismos 11 golpes, ya topados: el hoyo aporta +2 y no +7."""
        calculator = StablefordCalculator()
        scores = {**dict.fromkeys(range(1, 18), 4), 18: 11}

        totals = calculator.compute_participant_totals(
            handicap=0,
            holes=_course(),
            scores_by_hole=scores,
            cap_at_net_double_bogey=True,
        )

        # Los golpes de verdad no se tocan; lo que baja es lo computable
        assert totals.total_strokes == 79
        assert totals.to_par == 2

    def test_capping_does_not_move_the_stableford_points(self):
        """Un hoyo en net double bogey ya vale cero; peor sigue valiendo cero."""
        calculator = StablefordCalculator()
        scores = {**dict.fromkeys(range(1, 18), 4), 18: 11}

        raw = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole=scores
        )
        capped = calculator.compute_participant_totals(
            handicap=0,
            holes=_course(),
            scores_by_hole=scores,
            cap_at_net_double_bogey=True,
        )

        assert raw.stableford_points == capped.stableford_points


class TestResolveStrokesBasis:
    """De qué hándicap salen los golpes."""

    def test_without_a_tee_the_raw_handicap_is_used(self):
        """Quien no eligió tee juega su hándicap directamente."""
        calculator = StablefordCalculator()

        assert calculator.resolve_strokes_basis(12.4, None, 100) == Decimal("12.4")

    def test_with_a_tee_the_playing_handicap_is_used(self):
        calculator = StablefordCalculator()
        tee = TeeRating(course_rating=Decimal("71.8"), slope_rating=133, par=72)

        basis = calculator.resolve_strokes_basis(12.4, tee, 100)

        # PH = 12.4 x (133/113) + (71.8 - 72) = 14.594 - 0.2 = 14.394 -> 14
        assert basis == Decimal("14")

    def test_a_plus_player_keeps_a_negative_basis(self):
        """
        `calculate()` acota a cero y dejaría al plus sin ceder golpes; el
        frontend no acota, y es su resultado el que se ve hoy en la app.
        """
        calculator = StablefordCalculator()
        tee = TeeRating(course_rating=Decimal("71.8"), slope_rating=133, par=72)

        basis = calculator.resolve_strokes_basis(-2.0, tee, 100)

        assert basis < 0

    def test_no_handicap_gives_no_basis(self):
        calculator = StablefordCalculator()

        assert calculator.resolve_strokes_basis(None, None, 100) is None

    def test_allowance_reduces_the_basis(self):
        """El allowance recorta el hándicap de juego (Fourball 90 %, Foursomes 50 %)."""
        calculator = StablefordCalculator()
        tee = TeeRating(course_rating=Decimal("72.0"), slope_rating=113, par=72)

        full = calculator.resolve_strokes_basis(20.0, tee, 100)
        reduced = calculator.resolve_strokes_basis(20.0, tee, 50)

        assert full == Decimal("20")
        assert reduced == Decimal("10")


class TestFormatToPar:
    """Notación de golf."""

    @pytest.mark.parametrize(
        ("to_par", "expected"), [(0, "PAR"), (3, "+3"), (-2, "-2"), (1, "+1")]
    )
    def test_formats_like_a_scoreboard(self, to_par, expected):
        assert StablefordCalculator.format_to_par(to_par) == expected


class TestParityWithTheFrontend:
    """
    Vuelta completa contrastada contra el motor del frontend.

    Los valores esperados no están calculados a mano: salen de pasar estos
    mismos datos por `StablefordCalculator.js` y comprobar que ambos motores
    coinciden. Si alguien cambia las reglas en un solo lado, esto se cae, que
    es exactamente para lo que está.

    Campo con pares y stroke indexes irregulares a propósito: un campo de
    pares 4 y stroke index en orden esconde justo los errores de reparto.
    """

    PARS: ClassVar[list[int]] = [4, 5, 3, 4, 4, 3, 5, 4, 4, 4, 3, 5, 4, 4, 3, 4, 5, 4]
    STROKE_INDEXES: ClassVar[list[int]] = [7, 3, 15, 1, 11, 17, 5, 9, 13, 8, 16, 2, 10, 6, 18, 12, 4, 14]
    SCORES: ClassVar[dict[int, int]] = {
        1: 5, 2: 6, 3: 4, 4: 6, 5: 5, 6: 3, 7: 6, 8: 5, 9: 4,
        10: 5, 11: 4, 12: 7, 13: 5, 14: 4, 15: 3, 16: 5, 17: 6, 18: 5,
    }

    def _holes(self) -> list[HoleSetup]:
        return [
            HoleSetup(i + 1, self.PARS[i], self.STROKE_INDEXES[i]) for i in range(18)
        ]

    @pytest.mark.parametrize(
        ("handicap", "points", "gross", "net", "to_par"),
        [
            (0, 20, 88, 88, 16),
            (12.4, 32, 88, 76, 4),
            (18, 38, 88, 70, -2),
            (28, 48, 88, 60, -12),
            (-2, 18, 88, 90, 18),  # plus: cede golpes, juega peor que su bruto
        ],
    )
    def test_matches_the_values_the_frontend_produces(
        self, handicap, points, gross, net, to_par
    ):
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=handicap, holes=self._holes(), scores_by_hole=self.SCORES
        )

        assert totals.stableford_points == points
        assert totals.total_strokes == gross
        assert totals.net_strokes == net
        assert totals.to_par == to_par

    @pytest.mark.parametrize(
        ("handicap", "points", "gross", "net", "to_par"),
        [
            # El hoyo 1 es par 4 y su score real era 5. Con raya pasa a valer un
            # doble bogey: 6 de BRUTO en los dos casos —el bruto no depende del
            # reparto— y doble bogey NETO en lo que puntua, que es lo que le
            # quita el punto que el 5 daba.
            (0, 19, 89, 89, 17),
            (12.4, 30, 89, 78, 6),
        ],
    )
    def test_a_picked_up_hole_matches_the_frontend_too(
        self, handicap, points, gross, net, to_par
    ):
        """
        La raya es la parte mas facil de que los dos motores se separen: no hay
        numero anotado del que tirar, asi que cada lado tiene que inventar el
        mismo. Los valores salen de la misma vuelta de arriba con el hoyo 1
        recogido.
        """
        calculator = StablefordCalculator()
        scores: dict[int, int | None] = dict(self.SCORES)
        scores[1] = None

        totals = calculator.compute_participant_totals(
            handicap=handicap, holes=self._holes(), scores_by_hole=scores
        )

        assert totals.stableford_points == points
        assert totals.total_strokes == gross
        assert totals.net_strokes == net
        assert totals.to_par == to_par


class TestPickedUpHole:
    """
    La raya: el jugador recogio la bola y el hoyo se acabo sin numero.

    Se computa como doble bogey neto (Regla WHS 3.1), que es lo que manda
    anotar un hoyo no terminado. La distincion que sostiene todo esto es entre
    la clave AUSENTE —hoyo por jugar, no cuenta— y la clave presente con valor
    None —hoyo jugado y recogido, cuenta y vale cero puntos—.
    """

    def test_a_raya_counts_as_a_played_hole(self):
        """
        Given un hoyo anotado con raya
        When se agregan los totales
        Then el hoyo cuenta como jugado, con su par
        """
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: 4, 2: None}
        )

        assert totals.holes_played == 2
        assert totals.par_played == 8

    def test_a_raya_is_worth_no_points(self):
        """
        Given un hoyo recogido
        When se cuentan los puntos
        Then aporta cero, que es lo que vale recoger en Stableford
        """
        calculator = StablefordCalculator()

        con_raya = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: 4, 2: None}
        )
        solo_el_bueno = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: 4}
        )

        assert con_raya.stableford_points == solo_el_bueno.stableford_points

    def test_a_raya_is_charged_as_net_double_bogey(self):
        """
        Given un par 4 recogido sin recibir golpes
        When se suman los golpes
        Then cuenta 6, el doble bogey neto, y no cero
        """
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: None}
        )

        assert totals.total_strokes == 6
        assert totals.net_strokes == 6

    def test_the_gross_charge_does_not_depend_on_the_strokes_received(self):
        """
        Given la misma raya con y sin golpes recibidos
        When se miran los golpes brutos
        Then valen lo mismo: el bruto es un dato objetivo

        El neto si baja con los golpes —de ahi que siga siendo doble bogey neto
        y cero puntos—, pero el total de golpes no puede moverse con el
        allowance: la misma vuelta llegaba a dar 89 o 90 segun con que reparto
        se mirara.
        """
        calculator = StablefordCalculator()

        scratch = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: None}
        )
        con_golpe = calculator.compute_participant_totals(
            handicap=18, holes=_course(), scores_by_hole={1: None}
        )

        assert scratch.total_strokes == con_golpe.total_strokes == 6
        assert scratch.net_strokes == con_golpe.net_strokes == 6
        assert con_golpe.stableford_points == 0

    def test_a_missing_hole_still_does_not_count(self):
        """
        Given una tarjeta a la que le falta el hoyo 2
        When se agregan los totales
        Then ese hoyo no cuenta, a diferencia de uno con raya

        Es la trampa del cambio: `scores_by_hole.get(2)` devuelve None en los
        dos casos y significan lo contrario.
        """
        calculator = StablefordCalculator()

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole={1: 4}
        )

        assert totals.holes_played == 1
        assert totals.par_played == 4

    def test_a_raya_feeds_the_adjusted_gross_score(self):
        """
        Given una vuelta con un hoyo recogido
        When se calcula el Adjusted Gross Score del WHS
        Then el hoyo entra topado en su doble bogey neto

        Sin esto la vuelta con raya daria un diferencial mejor de lo jugado,
        que es justo lo que la Regla 3.1 evita.
        """
        calculator = StablefordCalculator()
        scores: dict[int, int | None] = dict.fromkeys(range(1, 19), 4)
        scores[1] = None

        totals = calculator.compute_participant_totals(
            handicap=0, holes=_course(), scores_by_hole=scores, cap_at_net_double_bogey=True
        )

        assert totals.adjusted_gross_strokes == 4 * 17 + 6
