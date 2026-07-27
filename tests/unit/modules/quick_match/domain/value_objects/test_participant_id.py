"""Tests para ParticipantId Value Object."""

import uuid

import pytest

from src.modules.quick_match.domain.value_objects.participant_id import (
    InvalidParticipantIdError,
    ParticipantId,
)


class TestParticipantId:
    def test_generate_creates_valid_id(self):
        pid = ParticipantId.generate()
        assert isinstance(pid.value, uuid.UUID)

    def test_accepts_uuid_string(self):
        u = uuid.uuid4()
        assert ParticipantId(str(u)).value == u

    def test_rejects_invalid_string(self):
        with pytest.raises(InvalidParticipantIdError):
            ParticipantId("not-a-uuid")

    def test_equality_and_hash(self):
        u = uuid.uuid4()
        assert ParticipantId(u) == ParticipantId(u)
        assert hash(ParticipantId(u)) == hash(ParticipantId(u))
