"""
Competition Golf Course ID Value Object.

Identificador único para cada asociación Competition-GolfCourse.
"""

from uuid import UUID, uuid4


class CompetitionGolfCourseId:
    """
    Value Object para el ID de la asociación Competition-GolfCourse.

    Responsabilidades:
    - Encapsular el UUID de la asociación
    - Validar que sea un UUID válido
    - Generar nuevos IDs únicos

    Características:
    - Inmutable (no se puede modificar después de crear)
    - Se compara por valor (equality by value)
    - Lightweight (solo encapsula un UUID)
    """

    def __init__(self, value: UUID | str):
        """
        Inicializa el ID.

        Args:
            value: UUID o string representando el ID

        Raises:
            ValueError: Si el valor no es un UUID válido
        """
        if isinstance(value, str):
            try:
                self._value = UUID(value)
            except ValueError as e:
                raise ValueError(f"Invalid UUID format: {value}") from e
        elif isinstance(value, UUID):
            self._value = value
        else:
            raise ValueError(f"CompetitionGolfCourseId must be UUID or str, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Retorna el UUID subyacente."""
        return self._value

    @classmethod
    def generate(cls) -> "CompetitionGolfCourseId":
        """
        Genera un nuevo ID único.

        Returns:
            CompetitionGolfCourseId con UUID v4 aleatorio
        """
        return cls(uuid4())

    def __eq__(self, other: object) -> bool:
        """Compara por valor (equality by value)."""
        if not isinstance(other, CompetitionGolfCourseId):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        """Permite usar en sets y como dict key."""
        return hash(self._value)

    def __str__(self) -> str:
        """Representación en string (para logs, debug)."""
        return str(self._value)

    def __repr__(self) -> str:
        """Representación técnica (para debugging)."""
        return f"CompetitionGolfCourseId({self._value!r})"
