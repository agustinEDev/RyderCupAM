"""
Tests unitarios para el Value Object MatchId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Comparación e igualdad
- Representación string
"""

import uuid

import pytest

from src.modules.competition.domain.value_objects.match_id import MatchId


class TestMatchIdGeneration:
    """Tests para la generación de MatchId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un MatchId
        Then: El valor es un UUID válido
        """
        # Act
        match_id = MatchId.generate()

        # Assert
        assert match_id is not None
        assert isinstance(match_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios MatchId
        Then: Todos son diferentes
        """
        # Act
        ids = [MatchId.generate() for _ in range(10)]

        # Assert
        id_values = [str(match_id.value) for match_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestMatchIdValidation:
    """Tests para la validación de MatchId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea MatchId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        match_id = MatchId(valid_uuid)

        # Assert
        assert str(match_id.value) == valid_uuid

    def test_valid_uuid_object_accepted(self):
        """
        Test: UUID object válido es aceptado
        Given: Objeto UUID válido
        When: Se crea MatchId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = uuid.uuid4()

        # Act
        match_id = MatchId(valid_uuid)

        # Assert
        assert match_id.value == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear MatchId
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            MatchId(invalid_uuid)

        assert "Invalid UUID format" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear MatchId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            MatchId("")

    def test_invalid_type_rejected(self):
        """
        Test: Tipo inválido es rechazado
        Given: Valor que no es UUID ni string
        When: Se intenta crear MatchId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            MatchId(123)

        assert "must be UUID or str" in str(exc_info.value)


class TestMatchIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: MatchId con mismo UUID son iguales
        Given: Dos MatchId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        match_id1 = MatchId(uuid_str)
        match_id2 = MatchId(uuid_str)

        # Act & Assert
        assert match_id1 == match_id2
        assert match_id1.value == match_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: MatchId con UUID diferentes no son iguales
        Given: Dos MatchId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        match_id1 = MatchId.generate()
        match_id2 = MatchId.generate()

        # Act & Assert
        assert match_id1 != match_id2

    def test_comparison_with_non_match_id_is_false(self):
        """
        Test: Comparación con objeto que no es MatchId es False
        Given: MatchId y string
        When: Se comparan
        Then: No son iguales
        """
        # Arrange
        match_id = MatchId.generate()

        # Act & Assert
        assert match_id != "some-string"
        assert match_id != 123
        assert match_id is not None

    def test_less_than_comparison(self):
        """
        Test: Operador < funciona correctamente
        Given: Dos MatchId con UUIDs diferentes
        When: Se comparan con <
        Then: La comparación es consistente
        """
        # Arrange
        id1 = MatchId("00000000-0000-0000-0000-000000000001")
        id2 = MatchId("00000000-0000-0000-0000-000000000002")

        # Act & Assert
        assert id1 < id2
        assert not id2 < id1

    def test_less_than_with_non_match_id_returns_not_implemented(self):
        """
        Test: < con tipo incompatible retorna NotImplemented
        Given: MatchId y string
        When: Se compara con <
        Then: Retorna NotImplemented (Python maneja TypeError)
        """
        # Arrange
        match_id = MatchId.generate()

        # Act & Assert
        with pytest.raises(TypeError):
            _ = match_id < "string"

    def test_hash_allows_usage_in_sets_and_dicts(self):
        """
        Test: __hash__ permite usar MatchId en sets y dicts
        Given: Varios MatchId
        When: Se usan como claves de dict o en set
        Then: Funcionan correctamente
        """
        # Arrange
        id1 = MatchId.generate()
        id2 = MatchId.generate()
        id3 = MatchId(str(id1.value))  # Mismo UUID que id1

        # Act
        id_set = {id1, id2, id3}
        id_dict = {id1: "value1", id2: "value2"}

        # Assert
        assert len(id_set) == 2  # id1 y id3 son el mismo
        assert id_dict[id1] == "value1"
        assert id_dict[id3] == "value1"  # Accede con el mismo valor


class TestMatchIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_uuid_string(self):
        """
        Test: __str__ retorna el UUID como string
        Given: MatchId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        match_id = MatchId.generate()

        # Act
        str_representation = str(match_id)

        # Assert
        assert str_representation == str(match_id.value)

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo para debugging
        Given: MatchId
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        match_id = MatchId.generate()

        # Act
        repr_str = repr(match_id)

        # Assert
        assert "MatchId" in repr_str
        assert str(match_id.value) in repr_str
