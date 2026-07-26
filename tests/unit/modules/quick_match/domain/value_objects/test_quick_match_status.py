"""Tests para QuickMatchStatus Value Object."""

from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus


class TestQuickMatchStatus:
    def test_pending_can_transition_to_in_progress_and_cancelled(self):
        assert QuickMatchStatus.PENDING.can_transition_to(QuickMatchStatus.IN_PROGRESS)
        assert QuickMatchStatus.PENDING.can_transition_to(QuickMatchStatus.CANCELLED)
        assert not QuickMatchStatus.PENDING.can_transition_to(QuickMatchStatus.COMPLETED)

    def test_in_progress_can_transition_to_completed_and_cancelled(self):
        assert QuickMatchStatus.IN_PROGRESS.can_transition_to(QuickMatchStatus.COMPLETED)
        assert QuickMatchStatus.IN_PROGRESS.can_transition_to(QuickMatchStatus.CANCELLED)
        assert not QuickMatchStatus.IN_PROGRESS.can_transition_to(QuickMatchStatus.PENDING)

    def test_terminal_states_have_no_transitions(self):
        for target in QuickMatchStatus:
            assert not QuickMatchStatus.COMPLETED.can_transition_to(target)
            assert not QuickMatchStatus.CANCELLED.can_transition_to(target)

    def test_is_final(self):
        assert QuickMatchStatus.COMPLETED.is_final()
        assert QuickMatchStatus.CANCELLED.is_final()
        assert not QuickMatchStatus.PENDING.is_final()
        assert not QuickMatchStatus.IN_PROGRESS.is_final()
