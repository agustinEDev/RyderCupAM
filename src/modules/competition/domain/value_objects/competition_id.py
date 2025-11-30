"""
CompetitionId Value Object - Identificador único de competición.

Este Value Object representa la identidad de una competición usando UUID.
"""

import uuid
from dataclasses import dataclass


class InvalidCompetitionIdError(Exception):
    """Excepción lanzada cuando un CompetitionId no es válido."""
    pass


@dataclass(frozen=True)
class CompetitionId:
    """
    Value Object para identificadores únicos de competición.

    Almacena internamente un objeto UUID, garantizando siempre un estado válido.
    Inmutable y validado automáticamente.

    Ejemplos:
        >>> # Generar nuevo ID
        >>> comp_id = CompetitionId.generate()
        >>> print(comp_id)
        'a1b2c3d4-...'

        >>> # Desde string UUID
        >>> comp_id2 = CompetitionId("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

        >>> # Desde objeto UUID
        >>> import uuid
        >>> comp_id3 = CompetitionId(uuid.uuid4())
    """

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        """
        Constructor que acepta tanto un objeto UUID como un string UUID.

        Args:
            value: UUID o string representando un UUID

        Raises:
            InvalidCompetitionIdError: Si el valor no es un UUID válido
        """
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidCompetitionIdError(
                    f"'{value}' no es un string UUID válido"
                ) from e
        else:
            raise InvalidCompetitionIdError(
                f"Se esperaba un UUID o un string, pero se recibió {type(value).__name__}"
            )

        # Usar object.__setattr__ porque la clase es frozen
        object.__setattr__(self, 'value', val)

    @classmethod
    def generate(cls) -> 'CompetitionId':
        """
        Genera un nuevo CompetitionId con un UUID v4 aleatorio.

        Returns:
            CompetitionId: Nuevo ID generado

        Ejemplos:
            >>> comp_id = CompetitionId.generate()
            >>> isinstance(comp_id.value, uuid.UUID)
            True
        """
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        """Representación string del UUID."""
        return str(self.value)

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, CompetitionId) and self.value == other.value

    def __lt__(self, other) -> bool:
        """Operador menor que (para ordenamiento)."""
        if not isinstance(other, CompetitionId):
            return NotImplemented
        return self.value < other.value

    def __hash__(self) -> int:
        """Hash del CompetitionId para uso en sets y dicts."""
        return hash(self.value)
