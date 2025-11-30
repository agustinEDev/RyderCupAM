"""Tests para EnrollmentStatus Value Object."""

from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus


class TestEnrollmentStatusTransitions:
    """Tests para transiciones de estado."""

    def test_requested_can_transition_to_approved(self):
        """REQUESTED puede ir a APPROVED."""
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.APPROVED)

    def test_requested_can_transition_to_rejected(self):
        """REQUESTED puede ir a REJECTED."""
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.REJECTED)

    def test_requested_can_transition_to_cancelled(self):
        """REQUESTED puede ir a CANCELLED (nuevo)."""
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.CANCELLED)

    def test_requested_cannot_transition_to_withdrawn(self):
        """REQUESTED NO puede ir a WITHDRAWN."""
        assert not EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.WITHDRAWN)

    def test_invited_can_transition_to_approved(self):
        """INVITED puede ir a APPROVED."""
        assert EnrollmentStatus.INVITED.can_transition_to(EnrollmentStatus.APPROVED)

    def test_invited_can_transition_to_cancelled(self):
        """INVITED puede ir a CANCELLED (jugador declina)."""
        assert EnrollmentStatus.INVITED.can_transition_to(EnrollmentStatus.CANCELLED)

    def test_approved_can_transition_to_withdrawn(self):
        """APPROVED puede ir a WITHDRAWN."""
        assert EnrollmentStatus.APPROVED.can_transition_to(EnrollmentStatus.WITHDRAWN)

    def test_approved_cannot_transition_to_cancelled(self):
        """APPROVED NO puede ir a CANCELLED (solo WITHDRAWN)."""
        assert not EnrollmentStatus.APPROVED.can_transition_to(EnrollmentStatus.CANCELLED)

    def test_rejected_cannot_transition(self):
        """REJECTED es estado final (no transiciones)."""
        assert not EnrollmentStatus.REJECTED.can_transition_to(EnrollmentStatus.APPROVED)
        assert not EnrollmentStatus.REJECTED.can_transition_to(EnrollmentStatus.WITHDRAWN)

    def test_cancelled_cannot_transition(self):
        """CANCELLED es estado final (no transiciones)."""
        assert not EnrollmentStatus.CANCELLED.can_transition_to(EnrollmentStatus.APPROVED)
        assert not EnrollmentStatus.CANCELLED.can_transition_to(EnrollmentStatus.WITHDRAWN)

    def test_withdrawn_cannot_transition(self):
        """WITHDRAWN es estado final (no transiciones)."""
        assert not EnrollmentStatus.WITHDRAWN.can_transition_to(EnrollmentStatus.APPROVED)
        assert not EnrollmentStatus.WITHDRAWN.can_transition_to(EnrollmentStatus.REQUESTED)


class TestEnrollmentStatusQueries:
    """Tests para métodos de consulta de estado."""

    def test_requested_is_pending(self):
        """REQUESTED es estado pendiente."""
        assert EnrollmentStatus.REQUESTED.is_pending()

    def test_invited_is_pending(self):
        """INVITED es estado pendiente."""
        assert EnrollmentStatus.INVITED.is_pending()

    def test_approved_is_not_pending(self):
        """APPROVED no es estado pendiente."""
        assert not EnrollmentStatus.APPROVED.is_pending()

    def test_approved_is_active(self):
        """APPROVED es estado activo."""
        assert EnrollmentStatus.APPROVED.is_active()

    def test_requested_is_not_active(self):
        """REQUESTED no es estado activo."""
        assert not EnrollmentStatus.REQUESTED.is_active()

    def test_rejected_is_final(self):
        """REJECTED es estado final."""
        assert EnrollmentStatus.REJECTED.is_final()

    def test_cancelled_is_final(self):
        """CANCELLED es estado final."""
        assert EnrollmentStatus.CANCELLED.is_final()

    def test_withdrawn_is_final(self):
        """WITHDRAWN es estado final."""
        assert EnrollmentStatus.WITHDRAWN.is_final()

    def test_approved_is_not_final(self):
        """APPROVED no es estado final (puede ir a WITHDRAWN)."""
        assert not EnrollmentStatus.APPROVED.is_final()

    def test_requested_is_not_final(self):
        """REQUESTED no es estado final."""
        assert not EnrollmentStatus.REQUESTED.is_final()


class TestEnrollmentStatusSemantics:
    """Tests para verificar la semántica correcta de los estados."""

    def test_cancelled_vs_rejected_semantics(self):
        """CANCELLED (jugador) vs REJECTED (creador) tienen transiciones diferentes."""
        # CANCELLED viene de acciones del jugador
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.CANCELLED)
        assert EnrollmentStatus.INVITED.can_transition_to(EnrollmentStatus.CANCELLED)

        # REJECTED viene de acciones del creador
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.REJECTED)

        # Ambos son finales
        assert EnrollmentStatus.CANCELLED.is_final()
        assert EnrollmentStatus.REJECTED.is_final()

    def test_cancelled_vs_withdrawn_semantics(self):
        """CANCELLED (pre-inscripción) vs WITHDRAWN (post-inscripción)."""
        # CANCELLED: antes de estar inscrito
        assert EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.CANCELLED)
        assert not EnrollmentStatus.APPROVED.can_transition_to(EnrollmentStatus.CANCELLED)

        # WITHDRAWN: después de estar inscrito
        assert EnrollmentStatus.APPROVED.can_transition_to(EnrollmentStatus.WITHDRAWN)
        assert not EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.WITHDRAWN)
