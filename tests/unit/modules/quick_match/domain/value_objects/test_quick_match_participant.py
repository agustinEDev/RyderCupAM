"""Tests para QuickMatchParticipant Value Object."""

from uuid import uuid4

import pytest

from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TestQuickMatchParticipant:
    def test_creates_with_no_team(self):
        p = QuickMatchParticipant(user_id=UserId(uuid4()))
        assert p.team is None

    def test_creates_with_valid_team(self):
        p = QuickMatchParticipant(user_id=UserId(uuid4()), team="A")
        assert p.team == "A"

    def test_rejects_invalid_team(self):
        with pytest.raises(ValueError, match="team debe ser"):
            QuickMatchParticipant(user_id=UserId(uuid4()), team="C")

    def test_equality_by_user_id_only(self):
        uid = UserId(uuid4())
        assert QuickMatchParticipant(user_id=uid, team="A") == QuickMatchParticipant(
            user_id=uid, team="B"
        )
