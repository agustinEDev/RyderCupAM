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

    def test_has_seven_states(self):
        # CANCELLED se añadió con la BE #359: la retira quien invita; ON_HOLD, el
        # 15 nov 2026: espera a que se reabra la inscripción (P1)
        assert len(InvitationStatus) == 7

    def test_on_hold_value(self):
        assert InvitationStatus.ON_HOLD == "ON_HOLD"

    def test_on_hold_is_open_not_pending_nor_final(self):
        assert InvitationStatus.ON_HOLD.is_open()
        assert InvitationStatus.ON_HOLD.is_on_hold()
        assert not InvitationStatus.ON_HOLD.is_pending()
        assert not InvitationStatus.ON_HOLD.is_final()
        assert InvitationStatus.PENDING.is_open()
        assert not InvitationStatus.PENDING.is_on_hold()
        assert not any(s.is_open() for s in InvitationStatus if s not in {"PENDING", "ON_HOLD"})

    def test_on_hold_transitions(self):
        """P1-P3: se llega desde PENDING; vuelve, se rechaza, se retira o sin plaza. Esperando
        no caduca: a EXPIRED no."""
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.ON_HOLD)
        assert {s for s in InvitationStatus if InvitationStatus.ON_HOLD.can_transition_to(s)} == {
            InvitationStatus.PENDING,
            InvitationStatus.DECLINED,
            InvitationStatus.NO_ROOM,
            InvitationStatus.CANCELLED,
        }
        assert not any(
            s.can_transition_to(InvitationStatus.ON_HOLD)
            for s in InvitationStatus
            if s != InvitationStatus.PENDING
        )

    def test_cancelled_value(self):
        assert InvitationStatus.CANCELLED == "CANCELLED"

    def test_cancelled_is_final_and_only_reached_from_pending(self):
        assert InvitationStatus.CANCELLED.is_final()
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.CANCELLED)
        assert not InvitationStatus.ACCEPTED.can_transition_to(InvitationStatus.CANCELLED)

    def test_no_room_value(self):
        """Rechazada por falta de plazas al cerrar la inscripción (#710, 24 sep)."""
        assert InvitationStatus.NO_ROOM == "NO_ROOM"

    def test_no_room_is_final(self):
        assert InvitationStatus.NO_ROOM.is_final()

    def test_pending_can_transition_to_no_room(self):
        assert InvitationStatus.PENDING.can_transition_to(InvitationStatus.NO_ROOM)

    def test_accepted_cannot_transition_to_no_room(self):
        assert not InvitationStatus.ACCEPTED.can_transition_to(InvitationStatus.NO_ROOM)


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

    def test_only_pending_and_on_hold_allow_transitions(self):
        """Solo PENDING y ON_HOLD permiten transiciones a otros estados."""
        for status in InvitationStatus:
            if status in (InvitationStatus.PENDING, InvitationStatus.ON_HOLD):
                assert not status.is_final()
            else:
                assert status.is_final()

    def test_all_terminal_states_have_no_transitions(self):
        """Todos los estados terminales tienen 0 transiciones validas."""
        terminal_states = [
            InvitationStatus.ACCEPTED,
            InvitationStatus.DECLINED,
            InvitationStatus.EXPIRED,
        ]
        for state in terminal_states:
            for target in InvitationStatus:
                assert not state.can_transition_to(target)
