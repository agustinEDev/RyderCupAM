"""Tests para QuickMatchHoleScore Entity."""

import pytest

from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidHoleScoreViolation,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId


def _make_hole_score(**overrides):
    defaults = {
        "id": QuickMatchHoleScoreId.generate(),
        "quick_match_id": QuickMatchId.generate(),
        "hole_number": 1,
        "participant_id": ParticipantId.generate(),
        "score": 4,
        "recorded_by_participant_id": ParticipantId.generate(),
    }
    defaults.update(overrides)
    return QuickMatchHoleScore.create(**defaults)


class TestQuickMatchHoleScoreCreate:
    def test_create_succeeds_with_valid_values(self):
        hs = _make_hole_score(hole_number=9, score=5)
        assert hs.hole_number == 9
        assert hs.score == 5

    def test_create_records_who_recorded_it(self):
        recorder = ParticipantId.generate()
        hs = _make_hole_score(recorded_by_participant_id=recorder)
        assert hs.recorded_by_participant_id == recorder

    @pytest.mark.parametrize("hole_number", [0, 19, -1])
    def test_create_rejects_invalid_hole_number(self, hole_number):
        with pytest.raises(InvalidHoleScoreViolation):
            _make_hole_score(hole_number=hole_number)

    @pytest.mark.parametrize("score", [0, 16, -3])
    def test_create_rejects_invalid_score(self, score):
        with pytest.raises(InvalidHoleScoreViolation):
            _make_hole_score(score=score)


class TestQuickMatchHoleScoreUpdate:
    def test_update_score_succeeds(self):
        hs = _make_hole_score(score=4)
        new_recorder = ParticipantId.generate()
        hs.update_score(6, recorded_by_participant_id=new_recorder)
        assert hs.score == 6
        assert hs.recorded_by_participant_id == new_recorder

    def test_update_score_rejects_invalid_value(self):
        hs = _make_hole_score()
        with pytest.raises(InvalidHoleScoreViolation):
            hs.update_score(20, recorded_by_participant_id=ParticipantId.generate())


class TestQuickMatchHoleScorePickedUp:
    """
    La raya: hoyo acabado sin numero porque el jugador recogio la bola.

    Se guarda como `score=None`, que NO es lo mismo que no tener fila: sin fila
    el hoyo esta por jugar, y con fila y raya esta jugado. De esa diferencia
    dependen la clasificacion en vivo y poder dar la partida por terminada.
    """

    def test_create_accepts_a_picked_up_hole(self):
        """
        Given un hoyo que el jugador no termino
        When se anota con score None
        Then la entidad lo acepta como raya, no como score fuera de rango
        """
        hs = _make_hole_score(score=None)

        assert hs.score is None
        assert hs.hole_number == 1

    def test_update_score_can_turn_a_number_into_a_raya(self):
        """
        Given un hoyo ya anotado con golpes
        When el anotador rectifica y pone raya
        Then el score queda en None y consta quien lo rectifico
        """
        hs = _make_hole_score(score=6)
        corrector = ParticipantId.generate()

        hs.update_score(None, recorded_by_participant_id=corrector)

        assert hs.score is None
        assert hs.recorded_by_participant_id == corrector

    def test_update_score_can_turn_a_raya_back_into_a_number(self):
        """
        Given un hoyo anotado con raya por error
        When se corrige con los golpes reales
        Then vuelve a tener numero
        """
        hs = _make_hole_score(score=None)

        hs.update_score(5, recorded_by_participant_id=ParticipantId.generate())

        assert hs.score == 5
