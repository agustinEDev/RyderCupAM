"""Tests para QuickMatchHoleScore Entity."""

from uuid import uuid4

import pytest

from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidHoleScoreViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.value_objects.user_id import UserId


def _make_hole_score(**overrides):
    defaults = {
        "id": QuickMatchHoleScoreId.generate(),
        "quick_match_id": QuickMatchId.generate(),
        "hole_number": 1,
        "player_user_id": UserId(uuid4()),
        "score": 4,
    }
    defaults.update(overrides)
    return QuickMatchHoleScore.create(**defaults)


class TestQuickMatchHoleScoreCreate:
    def test_create_succeeds_with_valid_values(self):
        hs = _make_hole_score(hole_number=9, score=5)
        assert hs.hole_number == 9
        assert hs.score == 5

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
        hs.update_score(6)
        assert hs.score == 6

    def test_update_score_rejects_invalid_value(self):
        hs = _make_hole_score()
        with pytest.raises(InvalidHoleScoreViolation):
            hs.update_score(20)
