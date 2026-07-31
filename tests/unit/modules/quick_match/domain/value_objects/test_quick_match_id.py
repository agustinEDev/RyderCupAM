"""Tests para QuickMatchId Value Object."""

import uuid

import pytest

from src.modules.quick_match.domain.value_objects.quick_match_id import (
    InvalidQuickMatchIdError,
    QuickMatchId,
)


class TestQuickMatchId:
    def test_generate_creates_valid_id(self):
        qid = QuickMatchId.generate()
        assert isinstance(qid.value, uuid.UUID)

    def test_accepts_uuid_string(self):
        u = uuid.uuid4()
        assert QuickMatchId(str(u)).value == u

    def test_rejects_invalid_string(self):
        with pytest.raises(InvalidQuickMatchIdError):
            QuickMatchId("not-a-uuid")

    def test_equality_and_hash(self):
        u = uuid.uuid4()
        assert QuickMatchId(u) == QuickMatchId(u)
        assert hash(QuickMatchId(u)) == hash(QuickMatchId(u))
