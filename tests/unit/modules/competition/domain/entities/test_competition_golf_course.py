"""
Tests unitarios para CompetitionGolfCourse Entity.

Verifica:
- Factory method create() con validaciones
- Reconstruct() para persistencia
- change_order() business method
- Equality e hashing (entity identity)
"""

from datetime import datetime

import pytest

from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.value_objects.competition_golf_course_id import (
    CompetitionGolfCourseId,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class TestCompetitionGolfCourseCreation:
    """Tests del factory method create()"""

    def test_create_with_valid_data(self):
        """
        Test: create() crea asociación válida
        Given: IDs válidos y display_order >= 1
        When: Llamamos a create()
        Then: Se crea correctamente con ID generado
        """
        # Arrange
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()

        # Act
        cgc = CompetitionGolfCourse.create(
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=1,
        )

        # Assert
        assert cgc.id is not None
        assert cgc.competition_id == competition_id
        assert cgc.golf_course_id == golf_course_id
        assert cgc.display_order == 1
        assert isinstance(cgc.created_at, datetime)

    def test_create_rejects_display_order_zero(self):
        """
        Test: create() rechaza display_order = 0
        Given: display_order = 0
        When: Llamamos a create()
        Then: Lanza ValueError
        """
        # Arrange
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            CompetitionGolfCourse.create(
                competition_id=competition_id,
                golf_course_id=golf_course_id,
                display_order=0,
            )

        assert "debe ser >= 1" in str(exc_info.value)

    def test_create_rejects_negative_display_order(self):
        """
        Test: create() rechaza display_order negativo
        Given: display_order < 0
        When: Llamamos a create()
        Then: Lanza ValueError
        """
        # Arrange
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()

        # Act & Assert
        with pytest.raises(ValueError):
            CompetitionGolfCourse.create(
                competition_id=competition_id,
                golf_course_id=golf_course_id,
                display_order=-1,
            )


class TestCompetitionGolfCourseReconstruct:
    """Tests del método reconstruct() para persistencia"""

    def test_reconstruct_from_database_data(self):
        """
        Test: reconstruct() hidrata desde BD sin validaciones
        Given: Datos de BD (ID existente + created_at)
        When: Llamamos a reconstruct()
        Then: Se reconstruye sin llamar a validaciones
        """
        # Arrange
        cgc_id = CompetitionGolfCourseId.generate()
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()
        created_at = datetime(2026, 1, 31, 20, 0, 0)

        # Act
        cgc = CompetitionGolfCourse.reconstruct(
            id=cgc_id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=2,
            created_at=created_at,
        )

        # Assert
        assert cgc.id == cgc_id
        assert cgc.competition_id == competition_id
        assert cgc.golf_course_id == golf_course_id
        assert cgc.display_order == 2
        assert cgc.created_at == created_at


class TestCompetitionGolfCourseChangeOrder:
    """Tests del business method change_order()"""

    def test_change_order_updates_display_order(self):
        """
        Test: change_order() actualiza el orden
        Given: Asociación con display_order = 1
        When: Llamamos a change_order(3)
        Then: display_order cambia a 3
        """
        # Arrange
        cgc = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        # Act
        cgc.change_order(3)

        # Assert
        assert cgc.display_order == 3

    def test_change_order_rejects_zero(self):
        """
        Test: change_order() rechaza 0
        Given: Asociación válida
        When: Llamamos a change_order(0)
        Then: Lanza ValueError
        """
        # Arrange
        cgc = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            cgc.change_order(0)

        assert "debe ser >= 1" in str(exc_info.value)

    def test_change_order_rejects_negative(self):
        """
        Test: change_order() rechaza negativos
        Given: Asociación válida
        When: Llamamos a change_order(-5)
        Then: Lanza ValueError
        """
        # Arrange
        cgc = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        # Act & Assert
        with pytest.raises(ValueError):
            cgc.change_order(-5)


class TestCompetitionGolfCourseEquality:
    """Tests de equality e hashing (Entity identity)"""

    def test_entities_with_same_id_are_equal(self):
        """
        Test: Entities con mismo ID son iguales
        Given: Dos instancias con mismo ID
        When: Comparamos con ==
        Then: Son iguales (identity por ID, no por atributos)
        """
        # Arrange
        cgc_id = CompetitionGolfCourseId.generate()
        competition_id = CompetitionId.generate()
        golf_course_id = GolfCourseId.generate()

        cgc1 = CompetitionGolfCourse.reconstruct(
            id=cgc_id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=1,
            created_at=datetime.now(),
        )

        cgc2 = CompetitionGolfCourse.reconstruct(
            id=cgc_id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=99,  # Diferente display_order, pero mismo ID
            created_at=datetime.now(),
        )

        # Act & Assert
        assert cgc1 == cgc2

    def test_entities_with_different_id_are_not_equal(self):
        """
        Test: Entities con diferente ID no son iguales
        Given: Dos instancias con IDs diferentes
        When: Comparamos con ==
        Then: No son iguales
        """
        # Arrange
        cgc1 = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        cgc2 = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        # Act & Assert
        assert cgc1 != cgc2

    def test_hash_allows_usage_in_sets(self):
        """
        Test: __hash__ permite usar en sets y dicts
        Given: Varias asociaciones
        When: Usamos en set
        Then: Funciona correctamente (identidad por ID)
        """
        # Arrange
        cgc1 = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=1,
        )

        cgc2 = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=2,
        )

        cgc3_same_id_as_1 = CompetitionGolfCourse.reconstruct(
            id=cgc1.id,
            competition_id=cgc1.competition_id,
            golf_course_id=cgc1.golf_course_id,
            display_order=99,
            created_at=cgc1.created_at,
        )

        # Act
        cgc_set = {cgc1, cgc2, cgc3_same_id_as_1}

        # Assert
        assert len(cgc_set) == 2  # cgc1 y cgc3 son el mismo por ID


class TestCompetitionGolfCourseRepresentation:
    """Tests de representación string"""

    def test_repr_is_informative(self):
        """
        Test: __repr__ es informativo para debugging
        Given: Asociación válida
        When: Obtenemos __repr__
        Then: Contiene información clave
        """
        # Arrange
        cgc = CompetitionGolfCourse.create(
            competition_id=CompetitionId.generate(),
            golf_course_id=GolfCourseId.generate(),
            display_order=3,
        )

        # Act
        repr_str = repr(cgc)

        # Assert
        assert "CompetitionGolfCourse" in repr_str
        assert "display_order=3" in repr_str
