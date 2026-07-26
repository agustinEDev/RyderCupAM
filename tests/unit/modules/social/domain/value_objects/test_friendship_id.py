"""Tests para FriendshipId Value Object."""

import uuid

import pytest

from src.modules.social.domain.value_objects.friendship_id import (
    FriendshipId,
    InvalidFriendshipIdError,
)


class TestFriendshipId:
    def test_generate_creates_valid_id(self):
        fid = FriendshipId.generate()
        assert isinstance(fid.value, uuid.UUID)

    def test_accepts_uuid_object(self):
        u = uuid.uuid4()
        fid = FriendshipId(u)
        assert fid.value == u

    def test_accepts_uuid_string(self):
        u = uuid.uuid4()
        fid = FriendshipId(str(u))
        assert fid.value == u

    def test_rejects_invalid_string(self):
        with pytest.raises(InvalidFriendshipIdError):
            FriendshipId("not-a-uuid")

    def test_rejects_invalid_type(self):
        with pytest.raises(InvalidFriendshipIdError):
            FriendshipId(12345)

    def test_equality(self):
        u = uuid.uuid4()
        assert FriendshipId(u) == FriendshipId(u)

    def test_inequality_different_values(self):
        assert FriendshipId.generate() != FriendshipId.generate()

    def test_hashable(self):
        fid = FriendshipId.generate()
        assert hash(fid) == hash(FriendshipId(fid.value))

    def test_str_representation(self):
        u = uuid.uuid4()
        assert str(FriendshipId(u)) == str(u)
