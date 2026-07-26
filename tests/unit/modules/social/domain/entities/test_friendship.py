"""Tests para Friendship Entity."""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.events.friendship_accepted_event import (
    FriendshipAcceptedEvent,
)
from src.modules.social.domain.events.friendship_blocked_event import (
    FriendshipBlockedEvent,
)
from src.modules.social.domain.events.friendship_declined_event import (
    FriendshipDeclinedEvent,
)
from src.modules.social.domain.events.friendship_requested_event import (
    FriendshipRequestedEvent,
)
from src.modules.social.domain.exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.domain.value_objects.user_id import UserId


def _make_friendship(**overrides):
    defaults = {
        "id": FriendshipId.generate(),
        "requester_id": UserId(uuid4()),
        "addressee_id": UserId(uuid4()),
    }
    defaults.update(overrides)
    return Friendship.create(**defaults)


class TestFriendshipCreate:
    def test_create_sets_pending_status(self):
        friendship = _make_friendship()
        assert friendship.status == FriendshipStatus.PENDING

    def test_create_emits_requested_event(self):
        friendship = _make_friendship()
        events = friendship.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], FriendshipRequestedEvent)

    def test_create_sets_timestamps(self):
        friendship = _make_friendship()
        assert friendship.created_at is not None
        assert friendship.updated_at is not None
        assert friendship.responded_at is None


class TestFriendshipCreateBlocked:
    def test_create_blocked_sets_blocked_status(self):
        blocker = UserId(uuid4())
        blocked = UserId(uuid4())
        friendship = Friendship.create_blocked(
            id=FriendshipId.generate(), blocker_id=blocker, blocked_id=blocked
        )
        assert friendship.status == FriendshipStatus.BLOCKED
        assert friendship.blocked_by == blocker

    def test_create_blocked_emits_blocked_event(self):
        friendship = Friendship.create_blocked(
            id=FriendshipId.generate(), blocker_id=UserId(uuid4()), blocked_id=UserId(uuid4())
        )
        events = friendship.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], FriendshipBlockedEvent)


class TestFriendshipAccept:
    def test_accept_from_pending_succeeds(self):
        friendship = _make_friendship()
        friendship.accept()
        assert friendship.status == FriendshipStatus.ACCEPTED
        assert friendship.responded_at is not None

    def test_accept_emits_accepted_event(self):
        friendship = _make_friendship()
        friendship.clear_domain_events()
        friendship.accept()
        events = friendship.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], FriendshipAcceptedEvent)

    def test_accept_when_already_accepted_raises(self):
        friendship = _make_friendship()
        friendship.accept()
        with pytest.raises(InvalidFriendshipStatusViolation):
            friendship.accept()

    def test_accept_when_declined_raises(self):
        friendship = _make_friendship()
        friendship.decline()
        with pytest.raises(InvalidFriendshipStatusViolation):
            friendship.accept()


class TestFriendshipDecline:
    def test_decline_from_pending_succeeds(self):
        friendship = _make_friendship()
        friendship.decline()
        assert friendship.status == FriendshipStatus.DECLINED

    def test_decline_emits_declined_event(self):
        friendship = _make_friendship()
        friendship.clear_domain_events()
        friendship.decline()
        events = friendship.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], FriendshipDeclinedEvent)

    def test_decline_when_accepted_raises(self):
        friendship = _make_friendship()
        friendship.accept()
        with pytest.raises(InvalidFriendshipStatusViolation):
            friendship.decline()


class TestFriendshipBlock:
    def test_block_from_pending_succeeds(self):
        friendship = _make_friendship()
        friendship.block(friendship.requester_id)
        assert friendship.status == FriendshipStatus.BLOCKED
        assert friendship.blocked_by == friendship.requester_id

    def test_block_from_accepted_succeeds(self):
        friendship = _make_friendship()
        friendship.accept()
        friendship.block(friendship.addressee_id)
        assert friendship.status == FriendshipStatus.BLOCKED
        assert friendship.blocked_by == friendship.addressee_id

    def test_block_when_already_blocked_raises(self):
        friendship = _make_friendship()
        friendship.block(friendship.requester_id)
        with pytest.raises(InvalidFriendshipStatusViolation):
            friendship.block(friendship.requester_id)

    def test_block_when_declined_raises(self):
        friendship = _make_friendship()
        friendship.decline()
        with pytest.raises(InvalidFriendshipStatusViolation):
            friendship.block(friendship.requester_id)


class TestFriendshipQueries:
    def test_involves_user_true_for_both_participants(self):
        friendship = _make_friendship()
        assert friendship.involves_user(friendship.requester_id)
        assert friendship.involves_user(friendship.addressee_id)

    def test_involves_user_false_for_third_party(self):
        friendship = _make_friendship()
        assert not friendship.involves_user(UserId(uuid4()))

    def test_other_user_id_returns_counterpart(self):
        friendship = _make_friendship()
        assert friendship.other_user_id(friendship.requester_id) == friendship.addressee_id
        assert friendship.other_user_id(friendship.addressee_id) == friendship.requester_id

    def test_other_user_id_raises_for_non_participant(self):
        friendship = _make_friendship()
        with pytest.raises(ValueError, match="no participa"):
            friendship.other_user_id(UserId(uuid4()))


class TestFriendshipReconstruct:
    def test_reconstruct_does_not_emit_events(self):
        friendship = Friendship.reconstruct(
            id=FriendshipId.generate(),
            requester_id=UserId(uuid4()),
            addressee_id=UserId(uuid4()),
            status=FriendshipStatus.ACCEPTED,
        )
        assert friendship.get_domain_events() == []

    def test_equality_by_id(self):
        fid = FriendshipId.generate()
        a = Friendship.reconstruct(
            id=fid,
            requester_id=UserId(uuid4()),
            addressee_id=UserId(uuid4()),
            status=FriendshipStatus.PENDING,
        )
        b = Friendship.reconstruct(
            id=fid,
            requester_id=UserId(uuid4()),
            addressee_id=UserId(uuid4()),
            status=FriendshipStatus.ACCEPTED,
        )
        assert a == b
