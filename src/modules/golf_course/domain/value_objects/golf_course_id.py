"""
GolfCourseId Value Object - Identificador único para campos de golf.
"""

import uuid


class GolfCourseId:
    """
    Value Object para identificador de campo de golf.

    Encapsula un UUID v4 único e inmutable.
    """

    def __init__(self, value: str) -> None:
        """
        Crea un GolfCourseId a partir de un UUID string.

        Args:
            value: UUID en formato string

        Raises:
            ValueError: Si el UUID no es válido
        """
        try:
            uuid_obj = uuid.UUID(value, version=4)
            self._value = str(uuid_obj)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid GolfCourseId: {value}") from e

    @classmethod
    def generate(cls) -> "GolfCourseId":
        """Genera un nuevo GolfCourseId aleatorio."""
        return cls(str(uuid.uuid4()))

    @property
    def value(self) -> str:
        """Retorna el UUID como string."""
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GolfCourseId):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"GolfCourseId({self._value})"
