"""Tests para MatchStatus enum."""

from src.modules.competition.domain.value_objects.match_status import MatchStatus


class TestMatchStatus:
    """Tests para MatchStatus"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert MatchStatus.SCHEDULED.value == "SCHEDULED"
        assert MatchStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert MatchStatus.COMPLETED.value == "COMPLETED"
        assert MatchStatus.WALKOVER.value == "WALKOVER"
        assert MatchStatus.CONCEDED.value == "CONCEDED"

    def test_is_finished_completed(self):
        """COMPLETED es un estado finalizado."""
        assert MatchStatus.COMPLETED.is_finished() is True

    def test_is_finished_walkover(self):
        """WALKOVER es un estado finalizado."""
        assert MatchStatus.WALKOVER.is_finished() is True

    def test_is_finished_scheduled(self):
        """SCHEDULED no es un estado finalizado."""
        assert MatchStatus.SCHEDULED.is_finished() is False

    def test_is_finished_in_progress(self):
        """IN_PROGRESS no es un estado finalizado."""
        assert MatchStatus.IN_PROGRESS.is_finished() is False

    def test_can_start_scheduled(self):
        """Solo SCHEDULED puede iniciarse."""
        assert MatchStatus.SCHEDULED.can_start() is True
        assert MatchStatus.IN_PROGRESS.can_start() is False
        assert MatchStatus.COMPLETED.can_start() is False

    def test_can_record_scores_in_progress(self):
        """Solo IN_PROGRESS permite registrar scores."""
        assert MatchStatus.IN_PROGRESS.can_record_scores() is True
        assert MatchStatus.SCHEDULED.can_record_scores() is False
        assert MatchStatus.COMPLETED.can_record_scores() is False

    def test_is_finished_conceded(self):
        """CONCEDED es un estado finalizado."""
        assert MatchStatus.CONCEDED.is_finished() is True

    def test_can_concede_in_progress(self):
        """Solo IN_PROGRESS permite conceder."""
        assert MatchStatus.IN_PROGRESS.can_concede() is True
        assert MatchStatus.SCHEDULED.can_concede() is False
        assert MatchStatus.COMPLETED.can_concede() is False
        assert MatchStatus.WALKOVER.can_concede() is False
        assert MatchStatus.CONCEDED.can_concede() is False

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(MatchStatus.SCHEDULED) == "SCHEDULED"
