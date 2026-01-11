"""
Handicap Value Object - Domain Layer

Representa el hándicap de golf de un usuario.
Inmutable y con validación de rango según reglas RFEG/EGA.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Handicap:
    """
    Value Object que representa el hándicap de golf de un usuario.

    Rango válido: -10.0 a 54.0 según reglas RFEG/EGA.
    Es inmutable y garantiza que solo existan hándicaps válidos.

    Examples:
        >>> handicap = Handicap(15.5)
        >>> str(handicap)
        '15.5'

        >>> Handicap(60.0)  # Lanza ValueError (rango inválido)
        >>> Handicap("15.5")  # Lanza TypeError (tipo inválido)
    """

    MIN_HANDICAP = -10.0
    MAX_HANDICAP = 54.0
    value: float

    def __post_init__(self):
        """Valida que el hándicap esté en el rango permitido."""
        if not isinstance(self.value, (int, float)):
            raise TypeError(
                f"El hándicap debe ser un número. Recibido: {type(self.value).__name__}"
            )

        if not self.MIN_HANDICAP <= self.value <= self.MAX_HANDICAP:
            raise ValueError(
                f"El hándicap debe estar entre {self.MIN_HANDICAP} y {self.MAX_HANDICAP}. "
                f"Recibido: {self.value}"
            )

    def __str__(self) -> str:
        """Representación en string con un decimal."""
        return f"{self.value:.1f}"

    def __float__(self) -> float:
        """Permite convertir a float directamente."""
        return self.value

    @classmethod
    def from_optional(cls, value: float | None) -> Optional["Handicap"]:
        """
        Crea un Handicap desde un valor opcional.

        Args:
            value: Valor del hándicap o None

        Returns:
            Handicap si value no es None, None en caso contrario
        """
        return cls(value) if value is not None else None
