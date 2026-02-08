"""Tests para TeamAssignmentMode enum."""

from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)


class TestTeamAssignmentMode:
    """Tests para TeamAssignmentMode"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert TeamAssignmentMode.AUTOMATIC.value == "AUTOMATIC"
        assert TeamAssignmentMode.MANUAL.value == "MANUAL"

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(TeamAssignmentMode.AUTOMATIC) == "AUTOMATIC"
        assert str(TeamAssignmentMode.MANUAL) == "MANUAL"

    def test_can_create_from_string(self):
        """Se puede crear desde string."""
        assert TeamAssignmentMode("AUTOMATIC") == TeamAssignmentMode.AUTOMATIC
        assert TeamAssignmentMode("MANUAL") == TeamAssignmentMode.MANUAL

    def test_is_string_subclass(self):
        """Es subclase de str."""
        assert isinstance(TeamAssignmentMode.AUTOMATIC, str)
