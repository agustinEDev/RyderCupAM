"""Tests para SessionType enum."""

from src.modules.competition.domain.value_objects.session_type import SessionType


class TestSessionType:
    """Tests para SessionType"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert SessionType.MORNING.value == "MORNING"
        assert SessionType.AFTERNOON.value == "AFTERNOON"
        assert SessionType.EVENING.value == "EVENING"

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(SessionType.MORNING) == "MORNING"
        assert str(SessionType.AFTERNOON) == "AFTERNOON"
        assert str(SessionType.EVENING) == "EVENING"

    def test_can_create_from_string(self):
        """Se puede crear desde string."""
        assert SessionType("MORNING") == SessionType.MORNING
        assert SessionType("AFTERNOON") == SessionType.AFTERNOON
        assert SessionType("EVENING") == SessionType.EVENING

    def test_is_string_subclass(self):
        """Es subclase de str para compatibilidad con JSON/DB."""
        assert isinstance(SessionType.MORNING, str)
