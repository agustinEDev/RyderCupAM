"""Tests para FriendshipStatus Value Object."""

from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus


class TestFriendshipStatus:
    def test_pending_is_pending(self):
        assert FriendshipStatus.PENDING.is_pending()
        assert not FriendshipStatus.ACCEPTED.is_pending()

    def test_accepted_is_accepted(self):
        assert FriendshipStatus.ACCEPTED.is_accepted()
        assert not FriendshipStatus.PENDING.is_accepted()

    def test_blocked_is_blocked(self):
        assert FriendshipStatus.BLOCKED.is_blocked()
        assert not FriendshipStatus.ACCEPTED.is_blocked()

    def test_final_states(self):
        assert FriendshipStatus.DECLINED.is_final()
        assert FriendshipStatus.BLOCKED.is_final()
        assert not FriendshipStatus.PENDING.is_final()
        assert not FriendshipStatus.ACCEPTED.is_final()

    def test_pending_can_transition_to_accepted_declined_blocked(self):
        assert FriendshipStatus.PENDING.can_transition_to(FriendshipStatus.ACCEPTED)
        assert FriendshipStatus.PENDING.can_transition_to(FriendshipStatus.DECLINED)
        assert FriendshipStatus.PENDING.can_transition_to(FriendshipStatus.BLOCKED)

    def test_accepted_can_only_transition_to_blocked(self):
        assert FriendshipStatus.ACCEPTED.can_transition_to(FriendshipStatus.BLOCKED)
        assert not FriendshipStatus.ACCEPTED.can_transition_to(FriendshipStatus.PENDING)
        assert not FriendshipStatus.ACCEPTED.can_transition_to(FriendshipStatus.DECLINED)

    def test_declined_and_blocked_are_terminal(self):
        for target in FriendshipStatus:
            assert not FriendshipStatus.DECLINED.can_transition_to(target)
            assert not FriendshipStatus.BLOCKED.can_transition_to(target)
