"""
Tests del reparto de golpes por hoyo, una sola pieza (BE #165).

Había tres copias: `PlayingHandicapCalculator.compute_strokes_received`
(competición), `StrokeAllocationService.allocate_by_hole` (partida rápida) y
`StrokePlayScoring.allocate_strokes` (Stableford). Esta es la que queda.
"""

import pytest

from src.shared.domain.services.stroke_allocation import (
    allocate_by_hole,
    holes_receiving_strokes,
    strokes_on_hole,
)

# Hoyos ordenados por stroke index, a propósito sin coincidir con su número:
# el reparto tiene que seguir la dificultad, no la numeración.
HOLES_BY_DIFFICULTY = [7, 3, 15, 1, 11, 5, 17, 9, 13, 2, 16, 4, 12, 8, 18, 6, 14, 10]


class TestStrokesOnHole:
    """Golpes de un hoyo, con signo: positivos los recibe, negativos los cede."""

    @pytest.mark.parametrize(
        ("playing_handicap", "stroke_index", "expected"),
        [
            (0, 1, 0),  # scratch
            (10, 10, 1),  # el último que recibe
            (10, 11, 0),  # ya no
            (18, 18, 1),  # uno en cada hoyo
            (20, 2, 2),  # vuelta completa más dos
            (20, 3, 1),
            (36, 18, 2),  # dos vueltas exactas
            (-2, 18, -1),  # el plus cede en el más fácil
            (-2, 17, -1),
            (-2, 16, 0),  # y no en el resto
            (-20, 18, -2),  # más de una vuelta cedida
            (-20, 16, -1),
        ],
    )
    def test_eighteen_holes(self, playing_handicap, stroke_index, expected):
        assert strokes_on_hole(playing_handicap, stroke_index) == expected

    @pytest.mark.parametrize(
        ("playing_handicap", "stroke_index", "expected"),
        [
            (5, 5, 1),
            (5, 6, 0),
            (11, 2, 2),  # da la vuelta a los 9
            (11, 3, 1),
            (-1, 9, -1),  # el más fácil de 9
            (-1, 8, 0),
        ],
    )
    def test_nine_holes(self, playing_handicap, stroke_index, expected):
        assert strokes_on_hole(playing_handicap, stroke_index, total_holes=9) == expected


class TestAllocateByHole:
    """El reparto entero, por número de hoyo."""

    def test_follows_the_difficulty_not_the_hole_number(self):
        assert allocate_by_hole(3, HOLES_BY_DIFFICULTY) == {7: 1, 3: 1, 15: 1}

    def test_wraps_around_past_the_last_hole(self):
        allocation = allocate_by_hole(23, HOLES_BY_DIFFICULTY)

        assert allocation[7] == 2  # SI 1
        assert allocation[11] == 2  # SI 5
        assert allocation[5] == 1  # SI 6
        assert allocation[10] == 1  # SI 18
        assert sum(allocation.values()) == 23

    def test_plus_gives_away_from_the_easiest(self):
        assert allocate_by_hole(-2, HOLES_BY_DIFFICULTY) == {14: -1, 10: -1}

    def test_only_lists_holes_with_strokes(self):
        assert allocate_by_hole(0, HOLES_BY_DIFFICULTY) == {}

    def test_no_holes_allocates_nothing(self):
        assert allocate_by_hole(10, []) == {}


class TestHolesReceivingStrokes:
    """
    La lista que guarda la competición: un hoyo aparece tantas veces como
    golpes recibe, vuelta a vuelta en orden de dificultad.
    """

    def test_one_pass(self):
        assert holes_receiving_strokes(3, HOLES_BY_DIFFICULTY) == [7, 3, 15]

    def test_second_pass_appends_in_difficulty_order(self):
        assert holes_receiving_strokes(20, HOLES_BY_DIFFICULTY) == [*HOLES_BY_DIFFICULTY, 7, 3]

    def test_zero_receives_nothing(self):
        assert holes_receiving_strokes(0, HOLES_BY_DIFFICULTY) == []

    def test_negative_receives_nothing(self):
        """
        La lista solo sabe de golpes recibidos. Hoy la competición recorta el
        plus a 0 antes de llegar aquí, y en match play nadie cede golpes.
        """
        assert holes_receiving_strokes(-3, HOLES_BY_DIFFICULTY) == []

    def test_no_holes_receives_nothing(self):
        assert holes_receiving_strokes(10, []) == []
