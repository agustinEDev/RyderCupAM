"""
GolfCourseId Value Object - Identificador único para campos de golf.
"""

import uuid


class GolfCourseId:
    """
    Value Object para identificador de campo de golf.

    Encapsula un UUID v4 único e inmutable.
    """

    def __init__(self, value: str | uuid.UUID) -> None:
        """
        Crea un GolfCourseId a partir de un UUID string o UUID object.

        Args:
            value: UUID en formato string o objeto UUID

        Raises:
            ValueError: Si el UUID no es válido
        """
        try:
            if isinstance(value, uuid.UUID):
                self._value = value
            else:
                self._value = uuid.UUID(value)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Invalid GolfCourseId: {value}") from e

    @classmethod
    def generate(cls) -> "GolfCourseId":
        """Genera un nuevo GolfCourseId aleatorio."""
        return cls(str(uuid.uuid4()))

    @classmethod
    def from_string(cls, value: str) -> "GolfCourseId":
        """
        Crea un GolfCourseId a partir de un string UUID.

        Alias de constructor para consistencia con otros Value Objects.

        Args:
            value: UUID en formato string

        Returns:
            Nueva instancia de GolfCourseId

        Raises:
            ValueError: Si el UUID no es válido
        """
        return cls(value)

    @property
    def value(self) -> uuid.UUID:
        """Retorna el UUID object."""
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GolfCourseId):
            return False
        return self._value == other._value

    def __lt__(self, other: "GolfCourseId") -> bool:
        """Less than comparison for sorting (required by SQLAlchemy)."""
        if not isinstance(other, GolfCourseId):
            return NotImplemented
        return self._value < other._value

    def __le__(self, other: "GolfCourseId") -> bool:
        """Less than or equal comparison for sorting."""
        if not isinstance(other, GolfCourseId):
            return NotImplemented
        return self._value <= other._value

    def __gt__(self, other: "GolfCourseId") -> bool:
        """Greater than comparison for sorting."""
        if not isinstance(other, GolfCourseId):
            return NotImplemented
        return self._value > other._value

    def __ge__(self, other: "GolfCourseId") -> bool:
        """Greater than or equal comparison for sorting."""
        if not isinstance(other, GolfCourseId):
            return NotImplemented
        return self._value >= other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"GolfCourseId({self._value})"
