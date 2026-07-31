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
