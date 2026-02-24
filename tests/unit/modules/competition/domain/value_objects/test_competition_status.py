"""Tests para CompetitionStatus Value Object - transiciones de estado."""

from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)


class TestCompetitionStatusForwardTransitions:
    """Tests para transiciones forward del ciclo de vida."""

    def test_draft_can_transition_to_active(self):
        """DRAFT → ACTIVE es válido."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.ACTIVE) is True

    def test_active_can_transition_to_closed(self):
        """ACTIVE → CLOSED es válido."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.CLOSED) is True

    def test_closed_can_transition_to_in_progress(self):
        """CLOSED → IN_PROGRESS es válido."""
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.IN_PROGRESS) is True

    def test_in_progress_can_transition_to_completed(self):
        """IN_PROGRESS → COMPLETED es válido."""
        assert CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.COMPLETED) is True

    def test_any_non_final_can_transition_to_cancelled(self):
        """Cualquier estado no final puede ir a CANCELLED."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.CANCELLED) is True
        assert (
            CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.CANCELLED) is True
        )


class TestCompetitionStatusBackwardTransitions:
    """Tests para transiciones backward (nueva funcionalidad)."""

    def test_in_progress_can_transition_to_closed(self):
        """IN_PROGRESS → CLOSED es válido (revertir para corregir schedule)."""
        assert CompetitionStatus.IN_PROGRESS.can_transition_to(CompetitionStatus.CLOSED) is True

    def test_closed_can_transition_to_active(self):
        """CLOSED → ACTIVE es válido (reabrir inscripciones)."""
        assert CompetitionStatus.CLOSED.can_transition_to(CompetitionStatus.ACTIVE) is True


class TestCompetitionStatusInvalidTransitions:
    """Tests para transiciones inválidas."""

    def test_completed_cannot_transition_to_closed(self):
        """COMPLETED → CLOSED es inválido (estado terminal)."""
        assert CompetitionStatus.COMPLETED.can_transition_to(CompetitionStatus.CLOSED) is False

    def test_cancelled_cannot_transition_to_anything(self):
        """CANCELLED no puede transicionar a ningún estado (estado terminal)."""
        for target in CompetitionStatus:
            assert CompetitionStatus.CANCELLED.can_transition_to(target) is False

    def test_completed_cannot_transition_to_anything(self):
        """COMPLETED no puede transicionar a ningún estado (estado terminal)."""
        for target in CompetitionStatus:
            assert CompetitionStatus.COMPLETED.can_transition_to(target) is False

    def test_draft_cannot_skip_to_closed(self):
        """DRAFT → CLOSED es inválido (no se puede saltar ACTIVE)."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.CLOSED) is False

    def test_draft_cannot_skip_to_in_progress(self):
        """DRAFT → IN_PROGRESS es inválido (no se puede saltar)."""
        assert CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.IN_PROGRESS) is False

    def test_active_cannot_skip_to_in_progress(self):
        """ACTIVE → IN_PROGRESS es inválido (no se puede saltar CLOSED)."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.IN_PROGRESS) is False

    def test_active_cannot_revert_to_draft(self):
        """ACTIVE → DRAFT es inválido (sin backward a DRAFT)."""
        assert CompetitionStatus.ACTIVE.can_transition_to(CompetitionStatus.DRAFT) is False


class TestCompetitionStatusHelpers:
    """Tests para métodos auxiliares."""

    def test_is_active_returns_true_for_active(self):
        """is_active() es True solo para ACTIVE."""
        assert CompetitionStatus.ACTIVE.is_active() is True
        assert CompetitionStatus.DRAFT.is_active() is False

    def test_is_final_returns_true_for_terminal_states(self):
        """is_final() es True para COMPLETED y CANCELLED."""
        assert CompetitionStatus.COMPLETED.is_final() is True
        assert CompetitionStatus.CANCELLED.is_final() is True
        assert CompetitionStatus.DRAFT.is_final() is False
        assert CompetitionStatus.IN_PROGRESS.is_final() is False

    def test_allows_modifications_returns_true_for_draft(self):
        """allows_modifications() es True solo para DRAFT."""
        assert CompetitionStatus.DRAFT.allows_modifications() is True
        assert CompetitionStatus.ACTIVE.allows_modifications() is False
