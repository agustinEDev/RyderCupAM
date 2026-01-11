"""
Tests unitarios para el Value Object PasswordHistoryId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Comparación e igualdad
- Representación string
"""

import uuid

import pytest

from src.modules.user.domain.value_objects.password_history_id import PasswordHistoryId


class TestPasswordHistoryIdGeneration:
    """Tests para la generación de PasswordHistoryId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un PasswordHistoryId
        Then: El valor es un UUID válido
        """
        # Act
        history_id = PasswordHistoryId.generate()

        # Assert
        assert history_id is not None
        assert isinstance(history_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios PasswordHistoryId
        Then: Todos son diferentes
        """
        # Act
        ids = [PasswordHistoryId.generate() for _ in range(10)]

        # Assert
        id_values = [str(history_id.value) for history_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestPasswordHistoryIdValidation:
    """Tests para la validación de PasswordHistoryId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea PasswordHistoryId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        history_id = PasswordHistoryId(valid_uuid)

        # Assert
        assert str(history_id.value) == valid_uuid

    def test_valid_uuid_object_accepted(self):
        """
        Test: UUID object válido es aceptado
        Given: Objeto UUID válido
        When: Se crea PasswordHistoryId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = uuid.uuid4()

        # Act
        history_id = PasswordHistoryId(valid_uuid)

        # Assert
        assert history_id.value == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear PasswordHistoryId
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PasswordHistoryId(invalid_uuid)

        assert "Invalid UUID format" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear PasswordHistoryId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            PasswordHistoryId("")

    def test_invalid_type_rejected(self):
        """
        Test: Tipo inválido es rechazado
        Given: Valor que no es UUID ni string
        When: Se intenta crear PasswordHistoryId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            PasswordHistoryId(123)

        assert "must be UUID or string" in str(exc_info.value)


class TestPasswordHistoryIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: PasswordHistoryId con mismo UUID son iguales
        Given: Dos PasswordHistoryId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        history_id1 = PasswordHistoryId(uuid_str)
        history_id2 = PasswordHistoryId(uuid_str)

        # Act & Assert
        assert history_id1 == history_id2
        assert history_id1.value == history_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: PasswordHistoryId con UUID diferentes no son iguales
        Given: Dos PasswordHistoryId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        history_id1 = PasswordHistoryId.generate()
        history_id2 = PasswordHistoryId.generate()

        # Act & Assert
        assert history_id1 != history_id2

    def test_comparison_with_non_password_history_id_is_false(self):
        """
        Test: Comparación con objeto que no es PasswordHistoryId es False
        Given: PasswordHistoryId y string
        When: Se comparan
        Then: No son iguales
        """
        # Arrange
        history_id = PasswordHistoryId.generate()

        # Act & Assert
        assert history_id != "some-string"
        assert history_id != 123
        assert history_id is not None

    def test_hash_allows_usage_in_sets_and_dicts(self):
        """
        Test: __hash__ permite usar PasswordHistoryId en sets y dicts
        Given: Varios PasswordHistoryId
        When: Se usan como claves de dict o en set
        Then: Funcionan correctamente
        """
        # Arrange
        id1 = PasswordHistoryId.generate()
        id2 = PasswordHistoryId.generate()
        id3 = PasswordHistoryId(str(id1.value))  # Mismo UUID que id1

        # Act
        id_set = {id1, id2, id3}
        id_dict = {id1: "value1", id2: "value2"}

        # Assert
        assert len(id_set) == 2  # id1 y id3 son el mismo
        assert id_dict[id1] == "value1"
        assert id_dict[id3] == "value1"  # Accede con el mismo valor


class TestPasswordHistoryIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_uuid_string(self):
        """
        Test: __str__ retorna el UUID como string
        Given: PasswordHistoryId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        history_id = PasswordHistoryId.generate()

        # Act
        str_representation = str(history_id)

        # Assert
        assert str_representation == str(history_id.value)

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo para debugging
        Given: PasswordHistoryId
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        history_id = PasswordHistoryId.generate()

        # Act
        repr_str = repr(history_id)

        # Assert
        assert "PasswordHistoryId" in repr_str
        assert str(history_id.value) in repr_str
