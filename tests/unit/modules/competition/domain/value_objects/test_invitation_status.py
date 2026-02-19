"""Tests para InvitationStatus Value Object."""

from src.modules.competition.domain.value_objects.invitation_status import (
    InvitationStatus,
)


class TestInvitationStatusValues:
    """Tests para los valores del enum."""

    def test_pending_value(self):
        assert InvitationStatus.PENDING == "PENDING"

    def test_accepted_value(self):
        assert InvitationStatus.ACCEPTED == "ACCEPTED"

    def test_declined_value(self):
        assert InvitationStatus.DECLINED == "DECLINED"

    def test_expired_value(self):
        assert InvitationStatus.EXPIRED == "EXPIRED"

    def test_has_four_states(self):
        assert len(InvitationStatus) == 4


class TestInvitationStatusTransitions:
    """Tests para transiciones de estado."""

    def test_pending_can_transition_to_accepted(self):
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.ACCEPTED)

    def test_pending_can_transition_to_declined(self):
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.DECLINED)

    def test_pending_can_transition_to_expired(self):
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.EXPIRED)

    def test_pending_cannot_transition_to_pending(self):
        assert not InvitationStatus.PENDING.can_transition_to(InvitationStatus.PENDING)

    def test_accepted_cannot_transition(self):
        """ACCEPTED es estado terminal."""
        assert not InvitationStatus.ACCEPTED.can_transition_to(InvitationStatus.PENDING)
        assert not InvitationStatus.ACCEPTED.can_transition_to(InvitationStatus.DECLINED)
        assert not InvitationStatus.ACCEPTED.can_transition_to(InvitationStatus.EXPIRED)

    def test_declined_cannot_transition(self):
        """DECLINED es estado terminal."""
        assert not InvitationStatus.DECLINED.can_transition_to(InvitationStatus.PENDING)
        assert not InvitationStatus.DECLINED.can_transition_to(InvitationStatus.ACCEPTED)
        assert not InvitationStatus.DECLINED.can_transition_to(InvitationStatus.EXPIRED)

    def test_expired_cannot_transition(self):
        """EXPIRED es estado terminal."""
        assert not InvitationStatus.EXPIRED.can_transition_to(InvitationStatus.PENDING)
        assert not InvitationStatus.EXPIRED.can_transition_to(InvitationStatus.ACCEPTED)
        assert not InvitationStatus.EXPIRED.can_transition_to(InvitationStatus.DECLINED)


class TestInvitationStatusQueries:
    """Tests para metodos de consulta."""

    def test_pending_is_pending(self):
        assert InvitationStatus.PENDING.is_pending()

    def test_accepted_is_not_pending(self):
        assert not InvitationStatus.ACCEPTED.is_pending()

    def test_declined_is_not_pending(self):
        assert not InvitationStatus.DECLINED.is_pending()

    def test_expired_is_not_pending(self):
        assert not InvitationStatus.EXPIRED.is_pending()

    def test_pending_is_not_final(self):
        assert not InvitationStatus.PENDING.is_final()

    def test_accepted_is_final(self):
        assert InvitationStatus.ACCEPTED.is_final()

    def test_declined_is_final(self):
        assert InvitationStatus.DECLINED.is_final()

    def test_expired_is_final(self):
        assert InvitationStatus.EXPIRED.is_final()


class TestInvitationStatusSemantics:
    """Tests para verificar la semantica de los estados."""

    def test_only_pending_allows_transitions(self):
        """Solo PENDING permite transiciones a otros estados."""
        for status in InvitationStatus:
            if status == InvitationStatus.PENDING:
                assert not status.is_final()
            else:
                assert status.is_final()

    def test_all_terminal_states_have_no_transitions(self):
        """Todos los estados terminales tienen 0 transiciones validas."""
        terminal_states = [InvitationStatus.ACCEPTED, InvitationStatus.DECLINED, InvitationStatus.EXPIRED]
        for state in terminal_states:
            for target in InvitationStatus:
                assert not state.can_transition_to(target)
