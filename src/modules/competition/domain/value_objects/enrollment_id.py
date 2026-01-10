"""
EnrollmentId Value Object - Identificador único de inscripción.

Este Value Object representa la identidad de una inscripción usando UUID.
"""

import uuid
from dataclasses import dataclass


class InvalidEnrollmentIdError(Exception):
    """Excepción lanzada cuando un EnrollmentId no es válido."""

    pass


@dataclass(frozen=True)
class EnrollmentId:
    """
    Value Object para identificadores únicos de inscripción.

    Almacena internamente un objeto UUID, garantizando siempre un estado válido.
    Inmutable y validado automáticamente.

    Ejemplos:
        >>> # Generar nuevo ID
        >>> enr_id = EnrollmentId.generate()

        >>> # Desde string UUID
        >>> enr_id2 = EnrollmentId("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    """

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | str):
        """
        Constructor que acepta tanto un objeto UUID como un string UUID.

        Args:
            value: UUID o string representando un UUID

        Raises:
            InvalidEnrollmentIdError: Si el valor no es un UUID válido
        """
        val = None
        if isinstance(value, uuid.UUID):
            val = value
        elif isinstance(value, str):
            try:
                val = uuid.UUID(value)
            except ValueError as e:
                raise InvalidEnrollmentIdError(
                    f"'{value}' no es un string UUID válido"
                ) from e
        else:
            raise InvalidEnrollmentIdError(
                f"Se esperaba un UUID o un string, pero se recibió {type(value).__name__}"
            )

        # Usar object.__setattr__ porque la clase es frozen
        object.__setattr__(self, "value", val)

    @classmethod
    def generate(cls) -> "EnrollmentId":
        """
        Genera un nuevo EnrollmentId con un UUID v4 aleatorio.

        Returns:
            EnrollmentId: Nuevo ID generado
        """
        return cls(uuid.uuid4())

    def __str__(self) -> str:
        """Representación string del UUID."""
        return str(self.value)

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, EnrollmentId) and self.value == other.value

    def __lt__(self, other) -> bool:
        """Operador menor que (para ordenamiento)."""
        if not isinstance(other, EnrollmentId):
            return NotImplemented
        return self.value < other.value

    def __hash__(self) -> int:
        """Hash del EnrollmentId para uso en sets y dicts."""
        return hash(self.value)
