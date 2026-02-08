"""Tests para ScheduleConfigMode enum."""

from src.modules.competition.domain.value_objects.schedule_config_mode import (
    ScheduleConfigMode,
)


class TestScheduleConfigMode:
    """Tests para ScheduleConfigMode"""

    def test_has_all_expected_values(self):
        """Verifica que existen todos los valores esperados."""
        assert ScheduleConfigMode.AUTOMATIC.value == "AUTOMATIC"
        assert ScheduleConfigMode.MANUAL.value == "MANUAL"

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(ScheduleConfigMode.AUTOMATIC) == "AUTOMATIC"
        assert str(ScheduleConfigMode.MANUAL) == "MANUAL"

    def test_can_create_from_string(self):
        """Se puede crear desde string."""
        assert ScheduleConfigMode("AUTOMATIC") == ScheduleConfigMode.AUTOMATIC
        assert ScheduleConfigMode("MANUAL") == ScheduleConfigMode.MANUAL

    def test_is_string_subclass(self):
        """Es subclase de str."""
        assert isinstance(ScheduleConfigMode.AUTOMATIC, str)
