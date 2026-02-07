"""
TeamAssignment ID Value Object.

Identificador único para asignaciones de equipos.
"""

from uuid import UUID, uuid4


class TeamAssignmentId:
    """
    Value Object para el ID de una asignación de equipos.

    Responsabilidades:
    - Encapsular el UUID de la asignación
    - Validar que sea un UUID válido
    - Generar nuevos IDs únicos
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
            raise ValueError(f"TeamAssignmentId must be UUID or str, got {type(value)}")

    @property
    def value(self) -> UUID:
        """Retorna el UUID subyacente."""
        return self._value

    @classmethod
    def generate(cls) -> "TeamAssignmentId":
        """Genera un nuevo ID único."""
        return cls(uuid4())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TeamAssignmentId):
            return False
        return self._value == other._value

    def __lt__(self, other: "TeamAssignmentId") -> bool:
        if not isinstance(other, TeamAssignmentId):
            return NotImplemented
        return self._value < other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"TeamAssignmentId({self._value!r})"
