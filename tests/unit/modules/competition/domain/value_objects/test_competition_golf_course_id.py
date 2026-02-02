"""
Tests unitarios para el Value Object CompetitionGolfCourseId.

Este archivo contiene tests que verifican:
- Generación de UUID válidos
- Validación de formato
- Comparación e igualdad
- Representación string
"""

import uuid

import pytest

from src.modules.competition.domain.value_objects.competition_golf_course_id import (
    CompetitionGolfCourseId,
)


class TestCompetitionGolfCourseIdGeneration:
    """Tests para la generación de CompetitionGolfCourseId"""

    def test_generate_creates_valid_uuid(self):
        """
        Test: generate() crea UUID válido
        Given: Llamada al método generate()
        When: Se genera un CompetitionGolfCourseId
        Then: El valor es un UUID válido
        """
        # Act
        cgc_id = CompetitionGolfCourseId.generate()

        # Assert
        assert cgc_id is not None
        assert isinstance(cgc_id.value, uuid.UUID)

    def test_generate_creates_unique_ids(self):
        """
        Test: generate() crea IDs únicos
        Given: Múltiples llamadas a generate()
        When: Se generan varios CompetitionGolfCourseId
        Then: Todos son diferentes
        """
        # Act
        ids = [CompetitionGolfCourseId.generate() for _ in range(10)]

        # Assert
        id_values = [str(cgc_id.value) for cgc_id in ids]
        assert len(set(id_values)) == 10  # Todos únicos


class TestCompetitionGolfCourseIdValidation:
    """Tests para la validación de CompetitionGolfCourseId"""

    def test_valid_uuid_string_accepted(self):
        """
        Test: UUID string válido es aceptado
        Given: String con formato UUID válido
        When: Se crea CompetitionGolfCourseId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Act
        cgc_id = CompetitionGolfCourseId(valid_uuid)

        # Assert
        assert str(cgc_id.value) == valid_uuid

    def test_valid_uuid_object_accepted(self):
        """
        Test: UUID object válido es aceptado
        Given: Objeto UUID válido
        When: Se crea CompetitionGolfCourseId
        Then: Se acepta sin errores
        """
        # Arrange
        valid_uuid = uuid.uuid4()

        # Act
        cgc_id = CompetitionGolfCourseId(valid_uuid)

        # Assert
        assert cgc_id.value == valid_uuid

    def test_invalid_uuid_string_rejected(self):
        """
        Test: UUID string inválido es rechazado
        Given: String que no es UUID válido
        When: Se intenta crear CompetitionGolfCourseId
        Then: Lanza ValueError
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CompetitionGolfCourseId(invalid_uuid)

        assert "Invalid UUID format" in str(exc_info.value)

    def test_empty_string_rejected(self):
        """
        Test: String vacío es rechazado
        Given: String vacío
        When: Se intenta crear CompetitionGolfCourseId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError):
            CompetitionGolfCourseId("")

    def test_invalid_type_rejected(self):
        """
        Test: Tipo inválido es rechazado
        Given: Valor que no es UUID ni string
        When: Se intenta crear CompetitionGolfCourseId
        Then: Lanza ValueError
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CompetitionGolfCourseId(123)

        assert "must be UUID or str" in str(exc_info.value)


class TestCompetitionGolfCourseIdComparison:
    """Tests para comparación e igualdad"""

    def test_same_uuid_are_equal(self):
        """
        Test: CompetitionGolfCourseId con mismo UUID son iguales
        Given: Dos CompetitionGolfCourseId con el mismo valor UUID
        When: Se comparan con ==
        Then: Son iguales
        """
        # Arrange
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        cgc_id1 = CompetitionGolfCourseId(uuid_str)
        cgc_id2 = CompetitionGolfCourseId(uuid_str)

        # Act & Assert
        assert cgc_id1 == cgc_id2
        assert cgc_id1.value == cgc_id2.value

    def test_different_uuid_are_not_equal(self):
        """
        Test: CompetitionGolfCourseId con UUID diferentes no son iguales
        Given: Dos CompetitionGolfCourseId generados
        When: Se comparan con ==
        Then: No son iguales
        """
        # Arrange
        cgc_id1 = CompetitionGolfCourseId.generate()
        cgc_id2 = CompetitionGolfCourseId.generate()

        # Act & Assert
        assert cgc_id1 != cgc_id2

    def test_comparison_with_non_competition_golf_course_id_is_false(self):
        """
        Test: Comparación con objeto que no es CompetitionGolfCourseId es False
        Given: CompetitionGolfCourseId y string
        When: Se comparan
        Then: No son iguales
        """
        # Arrange
        cgc_id = CompetitionGolfCourseId.generate()

        # Act & Assert
        assert cgc_id != "some-string"
        assert cgc_id != 123
        assert cgc_id is not None

    def test_hash_allows_usage_in_sets_and_dicts(self):
        """
        Test: __hash__ permite usar CompetitionGolfCourseId en sets y dicts
        Given: Varios CompetitionGolfCourseId
        When: Se usan como claves de dict o en set
        Then: Funcionan correctamente
        """
        # Arrange
        id1 = CompetitionGolfCourseId.generate()
        id2 = CompetitionGolfCourseId.generate()
        id3 = CompetitionGolfCourseId(str(id1.value))  # Mismo UUID que id1

        # Act
        id_set = {id1, id2, id3}
        id_dict = {id1: "value1", id2: "value2"}

        # Assert
        assert len(id_set) == 2  # id1 y id3 son el mismo
        assert id_dict[id1] == "value1"
        assert id_dict[id3] == "value1"  # Accede con el mismo valor


class TestCompetitionGolfCourseIdStringRepresentation:
    """Tests para representación string"""

    def test_str_returns_uuid_string(self):
        """
        Test: __str__ retorna el UUID como string
        Given: CompetitionGolfCourseId
        When: Se convierte a string
        Then: Retorna el valor UUID
        """
        # Arrange
        cgc_id = CompetitionGolfCourseId.generate()

        # Act
        str_representation = str(cgc_id)

        # Assert
        assert str_representation == str(cgc_id.value)

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo para debugging
        Given: CompetitionGolfCourseId
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        cgc_id = CompetitionGolfCourseId.generate()

        # Act
        repr_str = repr(cgc_id)

        # Assert
        assert "CompetitionGolfCourseId" in repr_str
        assert str(cgc_id.value) in repr_str
