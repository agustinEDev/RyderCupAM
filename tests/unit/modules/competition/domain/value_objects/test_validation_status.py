"""Tests para ValidationStatus Value Object."""

from src.modules.competition.domain.value_objects.validation_status import (
    ValidationStatus,
)


class TestValidationStatusValues:
    """Tests para los valores del enum."""

    def test_pending_value(self):
        assert ValidationStatus.PENDING == "PENDING"

    def test_match_value(self):
        assert ValidationStatus.MATCH == "MATCH"

    def test_mismatch_value(self):
        assert ValidationStatus.MISMATCH == "MISMATCH"

    def test_has_three_states(self):
        assert len(ValidationStatus) == 3

    def test_str_returns_value(self):
        """__str__ retorna el valor del enum."""
        assert str(ValidationStatus.PENDING) == "PENDING"
        assert str(ValidationStatus.MATCH) == "MATCH"
        assert str(ValidationStatus.MISMATCH) == "MISMATCH"

    def test_is_str_enum(self):
        """ValidationStatus es un StrEnum."""
        assert isinstance(ValidationStatus.PENDING, str)
