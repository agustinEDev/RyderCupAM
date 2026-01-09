"""Tests para CompetitionName Value Object."""

import pytest

from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
    InvalidCompetitionNameError,
)


class TestCompetitionNameCreation:
    """Tests para la creación de objetos CompetitionName."""

    def test_create_valid_name(self):
        """Debe crear un CompetitionName con nombre válido."""
        name = CompetitionName("Ryder Cup 2025")
        assert name.value == "Ryder Cup 2025"

    def test_create_name_with_lowercase(self):
        """Debe aplicar capitalización (Title Case)."""
        name = CompetitionName("ryder cup amateur")
        assert name.value == "Ryder Cup Amateur"

    def test_create_name_with_spaces(self):
        """Debe remover espacios al inicio y final."""
        name = CompetitionName("  Ryder Cup 2025  ")
        assert name.value == "Ryder Cup 2025"

    def test_create_name_with_mixed_case(self):
        """Debe normalizar capitalización correctamente."""
        name = CompetitionName("rYdEr CuP aMaTeUr")
        assert name.value == "Ryder Cup Amateur"


class TestCompetitionNameValidation:
    """Tests para la validación de nombres."""

    def test_empty_name_raises_error(self):
        """Nombre vacío debe lanzar InvalidCompetitionNameError."""
        with pytest.raises(
            InvalidCompetitionNameError, match="El nombre de la competición no puede estar vacío"
        ):
            CompetitionName("")

    def test_whitespace_only_name_raises_error(self):
        """Nombre con solo espacios debe lanzar error."""
        with pytest.raises(
            InvalidCompetitionNameError, match="El nombre de la competición no puede estar vacío"
        ):
            CompetitionName("   ")

    def test_name_exceeds_max_length_raises_error(self):
        """Nombre mayor a 100 caracteres debe lanzar error."""
        long_name = "A" * 101
        with pytest.raises(InvalidCompetitionNameError, match="no puede exceder 100 caracteres"):
            CompetitionName(long_name)

    def test_name_exactly_100_chars_is_valid(self):
        """Nombre de exactamente 100 caracteres es válido."""
        name_100 = "A" * 100
        name = CompetitionName(name_100)
        # Title case capitaliza la primera letra
        assert len(name.value) == 100

    def test_non_string_raises_error(self):
        """Tipo no string debe lanzar error."""
        with pytest.raises(InvalidCompetitionNameError, match="El nombre debe ser un string"):
            CompetitionName(123)


class TestCompetitionNameEquality:
    """Tests para comparación de nombres."""

    def test_same_names_are_equal(self):
        """Nombres iguales deben ser iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        assert name1 == name2

    def test_different_names_are_not_equal(self):
        """Nombres diferentes no son iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Masters 2025")
        assert name1 != name2

    def test_normalized_names_are_equal(self):
        """Nombres normalizados iguales son iguales."""
        name1 = CompetitionName("ryder cup")
        name2 = CompetitionName("RYDER CUP")
        assert name1 == name2

    def test_hash_is_consistent(self):
        """Hash debe ser consistente para nombres iguales."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        assert hash(name1) == hash(name2)

    def test_can_use_in_set(self):
        """Debe poder usarse en sets."""
        name1 = CompetitionName("Ryder Cup 2025")
        name2 = CompetitionName("Ryder Cup 2025")
        name3 = CompetitionName("Masters 2025")

        names_set = {name1, name2, name3}
        assert len(names_set) == 2  # name1 y name2 son iguales


class TestCompetitionNameStringRepresentation:
    """Tests para representación string."""

    def test_str_returns_value(self):
        """__str__ debe retornar el valor."""
        name = CompetitionName("Ryder Cup 2025")
        assert str(name) == "Ryder Cup 2025"
