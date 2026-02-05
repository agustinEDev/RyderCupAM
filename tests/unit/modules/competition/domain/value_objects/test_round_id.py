"""
Tests unitarios para el Value Object RoundId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Comparación e igualdad
- Representación string
"""

import uuid

import pytest

from src.modules.competition.domain.value_objects.round_id import RoundId


class TestRoundIdGeneration:
    """Tests para la generación de RoundId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un RoundId
        Then: El valor es un UUID válido
        """
        # Act
        round_id = RoundId.generate()

        # Assert
        assert round_id is not None
        assert isinstance(round_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios RoundId
        Then: Todos son diferentes
        """
        # Act
        ids = [RoundId.generate() for _ in range(10)]

        # Assert
        id_values = [str(round_id.value) for round_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestRoundIdValidation:
    """Tests para la validación de RoundId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea RoundId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        round_id = RoundId(valid_uuid)

        # Assert
        assert str(round_id.value) == valid_uuid

    def test_valid_uuid_object_accepted(self):
        """
        Test: UUID object válido es aceptado
        Given: Objeto UUID válido
        When: Se crea RoundId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = uuid.uuid4()

        # Act
        round_id = RoundId(valid_uuid)

        # Assert
        assert round_id.value == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear RoundId
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            RoundId(invalid_uuid)

        assert "Invalid UUID format" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear RoundId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            RoundId("")

    def test_invalid_type_rejected(self):
        """
        Test: Tipo inválido es rechazado
        Given: Valor que no es UUID ni string
        When: Se intenta crear RoundId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            RoundId(123)

        assert "must be UUID or str" in str(exc_info.value)


class TestRoundIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: RoundId con mismo UUID son iguales
        Given: Dos RoundId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        round_id1 = RoundId(uuid_str)
        round_id2 = RoundId(uuid_str)

        # Act & Assert
        assert round_id1 == round_id2
        assert round_id1.value == round_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: RoundId con UUID diferentes no son iguales
        Given: Dos RoundId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        round_id1 = RoundId.generate()
        round_id2 = RoundId.generate()

        # Act & Assert
        assert round_id1 != round_id2

    def test_comparison_with_non_round_id_is_false(self):
        """
        Test: Comparación con objeto que no es RoundId es False
        Given: RoundId y string
        When: Se comparan
        Then: No son iguales
        """
        # Arrange
        round_id = RoundId.generate()

        # Act & Assert
        assert round_id != "some-string"
        assert round_id != 123
        assert round_id is not None

    def test_less_than_comparison(self):
        """
        Test: Operador < funciona correctamente
        Given: Dos RoundId con UUIDs diferentes
        When: Se comparan con <
        Then: La comparación es consistente
        """
        # Arrange
        id1 = RoundId("00000000-0000-0000-0000-000000000001")
        id2 = RoundId("00000000-0000-0000-0000-000000000002")

        # Act & Assert
        assert id1 < id2
        assert not id2 < id1

    def test_less_than_with_non_round_id_returns_not_implemented(self):
        """
        Test: < con tipo incompatible retorna NotImplemented
        Given: RoundId y string
        When: Se compara con <
        Then: Retorna NotImplemented (Python maneja TypeError)
        """
        # Arrange
        round_id = RoundId.generate()

        # Act & Assert
        with pytest.raises(TypeError):
            _ = round_id < "string"

    def test_hash_allows_usage_in_sets_and_dicts(self):
        """
        Test: __hash__ permite usar RoundId en sets y dicts
        Given: Varios RoundId
        When: Se usan como claves de dict o en set
        Then: Funcionan correctamente
        """
        # Arrange
        id1 = RoundId.generate()
        id2 = RoundId.generate()
        id3 = RoundId(str(id1.value))  # Mismo UUID que id1

        # Act
        id_set = {id1, id2, id3}
        id_dict = {id1: "value1", id2: "value2"}

        # Assert
        assert len(id_set) == 2  # id1 y id3 son el mismo
        assert id_dict[id1] == "value1"
        assert id_dict[id3] == "value1"  # Accede con el mismo valor


class TestRoundIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_uuid_string(self):
        """
        Test: __str__ retorna el UUID como string
        Given: RoundId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        round_id = RoundId.generate()

        # Act
        str_representation = str(round_id)

        # Assert
        assert str_representation == str(round_id.value)

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo para debugging
        Given: RoundId
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        round_id = RoundId.generate()

        # Act
        repr_str = repr(round_id)

        # Assert
        assert "RoundId" in repr_str
        assert str(round_id.value) in repr_str
