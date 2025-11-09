"""
Tests for Handicap Value Object
"""

import pytest
from src.modules.user.domain.value_objects.handicap import Handicap


class TestHandicapCreation:
    """Tests para la creación del Value Object Handicap."""

    def test_create_valid_handicap_positive(self):
        """Test: Crear hándicap con valor positivo válido."""
        handicap = Handicap(15.5)
        assert handicap.value == 15.5

    def test_create_valid_handicap_negative(self):
        """Test: Crear hándicap con valor negativo válido."""
        handicap = Handicap(-5.0)
        assert handicap.value == -5.0

    def test_create_handicap_zero(self):
        """Test: Crear hándicap con valor cero."""
        handicap = Handicap(0.0)
        assert handicap.value == 0.0

    def test_create_handicap_minimum_valid(self):
        """Test: Crear hándicap con valor mínimo válido (-10.0)."""
        handicap = Handicap(-10.0)
        assert handicap.value == -10.0

    def test_create_handicap_maximum_valid(self):
        """Test: Crear hándicap con valor máximo válido (54.0)."""
        handicap = Handicap(54.0)
        assert handicap.value == 54.0

    def test_create_handicap_with_integer(self):
        """Test: Crear hándicap con valor entero (se convierte a float)."""
        handicap = Handicap(20)
        assert handicap.value == 20
        assert isinstance(handicap.value, (int, float))


class TestHandicapValidation:
    """Tests para la validación de hándicap."""

    def test_handicap_below_minimum_raises_error(self):
        """Test: Crear hándicap por debajo del mínimo lanza ValueError."""
        with pytest.raises(ValueError, match=r"debe estar entre -10\.0 y 54\.0"):
            Handicap(-10.1)

    def test_handicap_above_maximum_raises_error(self):
        """Test: Crear hándicap por encima del máximo lanza ValueError."""
        with pytest.raises(ValueError, match=r"debe estar entre -10\.0 y 54\.0"):
            Handicap(54.1)

    def test_handicap_with_invalid_type_raises_error(self):
        """Test: Crear hándicap con tipo inválido lanza TypeError."""
        with pytest.raises(TypeError, match="debe ser un número"):
            Handicap("15.5")

    def test_handicap_with_none_raises_error(self):
        """Test: Crear hándicap con None lanza TypeError."""
        with pytest.raises(TypeError):
            Handicap(None)


class TestHandicapBehavior:
    """Tests para el comportamiento del Value Object Handicap."""

    def test_handicap_is_immutable(self):
        """Test: El hándicap es inmutable (frozen dataclass)."""
        handicap = Handicap(15.5)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            handicap.value = 20.0

    def test_handicap_str_representation(self):
        """Test: Representación string del hándicap con un decimal."""
        handicap = Handicap(15.5)
        assert str(handicap) == "15.5"

    def test_handicap_str_representation_integer_value(self):
        """Test: Representación string con valor entero muestra un decimal."""
        handicap = Handicap(20.0)
        assert str(handicap) == "20.0"

    def test_handicap_float_conversion(self):
        """Test: Conversión a float del hándicap."""
        handicap = Handicap(15.5)
        assert float(handicap) == 15.5

    def test_handicap_equality(self):
        """Test: Dos hándicaps con el mismo valor son iguales."""
        handicap1 = Handicap(15.5)
        handicap2 = Handicap(15.5)
        assert handicap1 == handicap2

    def test_handicap_inequality(self):
        """Test: Dos hándicaps con diferente valor no son iguales."""
        handicap1 = Handicap(15.5)
        handicap2 = Handicap(20.0)
        assert handicap1 != handicap2


class TestHandicapFromOptional:
    """Tests para el método factory from_optional."""

    def test_from_optional_with_value(self):
        """Test: Crear hándicap desde valor opcional (no None)."""
        handicap = Handicap.from_optional(15.5)
        assert handicap is not None
        assert handicap.value == 15.5

    def test_from_optional_with_none(self):
        """Test: Crear hándicap desde None devuelve None."""
        handicap = Handicap.from_optional(None)
        assert handicap is None

    def test_from_optional_with_zero(self):
        """Test: Crear hándicap desde cero (valor válido)."""
        handicap = Handicap.from_optional(0.0)
        assert handicap is not None
        assert handicap.value == 0.0

    def test_from_optional_with_invalid_value_raises_error(self):
        """Test: from_optional con valor inválido lanza ValueError."""
        with pytest.raises(ValueError):
            Handicap.from_optional(100.0)
