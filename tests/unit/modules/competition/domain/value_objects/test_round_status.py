"""Tests para RoundStatus enum."""

from src.modules.competition.domain.value_objects.round_status import RoundStatus


class TestRoundStatus:
    """Tests para RoundStatus"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert RoundStatus.PENDING_TEAMS.value == "PENDING_TEAMS"
        assert RoundStatus.PENDING_MATCHES.value == "PENDING_MATCHES"
        assert RoundStatus.SCHEDULED.value == "SCHEDULED"
        assert RoundStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert RoundStatus.COMPLETED.value == "COMPLETED"

    def test_can_generate_matches_pending_matches(self):
        """Solo PENDING_MATCHES permite generar partidos."""
        assert RoundStatus.PENDING_MATCHES.can_generate_matches() is True
        assert RoundStatus.PENDING_TEAMS.can_generate_matches() is False
        assert RoundStatus.SCHEDULED.can_generate_matches() is False

    def test_can_modify_pending_states(self):
        """Solo estados PENDING permiten modificaciones."""
        assert RoundStatus.PENDING_TEAMS.can_modify() is True
        assert RoundStatus.PENDING_MATCHES.can_modify() is True
        assert RoundStatus.SCHEDULED.can_modify() is False
        assert RoundStatus.IN_PROGRESS.can_modify() is False
        assert RoundStatus.COMPLETED.can_modify() is False

    def test_is_finished_completed(self):
        """Solo COMPLETED es estado finalizado."""
        assert RoundStatus.COMPLETED.is_finished() is True
        assert RoundStatus.IN_PROGRESS.is_finished() is False
        assert RoundStatus.SCHEDULED.is_finished() is False

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(RoundStatus.PENDING_TEAMS) == "PENDING_TEAMS"
