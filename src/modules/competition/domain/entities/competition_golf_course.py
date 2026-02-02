"""
Competition Golf Course Entity - Association Entity.

Representa la asociación Many-to-Many entre Competition y GolfCourse.
"""

from datetime import datetime

from src.modules.competition.domain.value_objects.competition_golf_course_id import (
    CompetitionGolfCourseId,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class CompetitionGolfCourse:
    """
    Entidad de asociación entre Competition y GolfCourse.

    Responsabilidades:
    - Representar la relación Many-to-Many con metadatos
    - Mantener el orden de los campos (display_order)
    - Validar cambios en el orden
    - Encapsular datos de la asociación

    Características DDD:
    - Es una Entity (tiene identidad: CompetitionGolfCourseId)
    - NO es un Agregado Raíz (vive dentro de Competition)
    - Tiene ciclo de vida controlado por Competition

    Ejemplo:
        >>> cgc = CompetitionGolfCourse.create(
        ...     competition_id=CompetitionId.generate(),
        ...     golf_course_id=GolfCourseId.generate(),
        ...     display_order=1
        ... )
        >>> cgc.change_order(2)  # Cambia el orden
    """

    def __init__(
        self,
        id: CompetitionGolfCourseId,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        display_order: int,
        created_at: datetime,
    ):
        """
        Constructor privado (usar factory method create()).

        Args:
            id: Identificador único de la asociación
            competition_id: ID de la competición
            golf_course_id: ID del campo de golf
            display_order: Orden de visualización (1, 2, 3...)
            created_at: Timestamp de creación
        """
        self._id = id
        self._competition_id = competition_id
        self._golf_course_id = golf_course_id
        self._display_order = display_order
        self._created_at = created_at

    @classmethod
    def create(
        cls,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        display_order: int,
    ) -> "CompetitionGolfCourse":
        """
        Factory method para crear una nueva asociación.

        Args:
            competition_id: ID de la competición
            golf_course_id: ID del campo de golf
            display_order: Orden de visualización (debe ser >= 1)

        Returns:
            Nueva instancia de CompetitionGolfCourse

        Raises:
            ValueError: Si display_order < 1
        """
        if display_order < 1:
            raise ValueError(f"display_order debe ser >= 1, recibido: {display_order}")

        return cls(
            id=CompetitionGolfCourseId.generate(),
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=display_order,
            created_at=datetime.now(),
        )

    @classmethod
    def reconstruct(
        cls,
        id: CompetitionGolfCourseId,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        display_order: int,
        created_at: datetime,
    ) -> "CompetitionGolfCourse":
        """
        Reconstruye una asociación desde la BD (sin validaciones).

        Usado por el Repository para hidratar entidades desde persistencia.

        Args:
            id: ID existente
            competition_id: ID de la competición
            golf_course_id: ID del campo
            display_order: Orden actual
            created_at: Timestamp original

        Returns:
            Instancia reconstruida
        """
        return cls(
            id=id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            display_order=display_order,
            created_at=created_at,
        )

    # ==================== Business Methods ====================

    def change_order(self, new_order: int) -> None:
        """
        Cambia el orden de visualización del campo.

        Business Rule: El orden debe ser >= 1

        Args:
            new_order: Nuevo orden de visualización

        Raises:
            ValueError: Si new_order < 1
        """
        if new_order < 1:
            raise ValueError(f"display_order debe ser >= 1, recibido: {new_order}")

        self._display_order = new_order

    # ==================== Properties (Read-Only) ====================

    @property
    def id(self) -> CompetitionGolfCourseId:
        """Identificador único de la asociación."""
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        """ID de la competición."""
        return self._competition_id

    @property
    def golf_course_id(self) -> GolfCourseId:
        """ID del campo de golf."""
        return self._golf_course_id

    @property
    def display_order(self) -> int:
        """Orden de visualización del campo."""
        return self._display_order

    @property
    def created_at(self) -> datetime:
        """Timestamp de creación de la asociación."""
        return self._created_at

    # ==================== Equality & Hashing ====================

    def __eq__(self, other: object) -> bool:
        """
        Compara por identidad (ID).

        Entities se comparan por ID, NO por atributos.
        """
        if not isinstance(other, CompetitionGolfCourse):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        """Permite usar en sets y como dict key."""
        return hash(self._id)

    def __repr__(self) -> str:
        """Representación técnica para debugging."""
        return (
            f"CompetitionGolfCourse("
            f"id={self._id}, "
            f"competition_id={self._competition_id}, "
            f"golf_course_id={self._golf_course_id}, "
            f"display_order={self._display_order})"
        )
