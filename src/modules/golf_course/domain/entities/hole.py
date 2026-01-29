"""
Hole Entity - Hoyo individual de un campo de golf.
"""

from dataclasses import dataclass


@dataclass
class Hole:
    """
    Hoyo de un campo de golf.

    Attributes:
        number: Número del hoyo (1-18)
        par: Par del hoyo (3, 4, 5)
        stroke_index: Índice de dificultad (1-18, único por campo)

    Validations:
        - number: 1-18
        - par: 3, 4, o 5
        - stroke_index: 1-18 (debe ser único en el campo)
        - Total par del campo: 66-76

    Example:
        >>> hole = Hole(number=1, par=4, stroke_index=5)
    """

    number: int
    par: int
    stroke_index: int

    def __post_init__(self) -> None:
        """Valida los valores del hoyo."""
        if not (1 <= self.number <= 18):  # noqa: PLR2004
            raise ValueError(f"Hole number must be between 1 and 18, got {self.number}")

        if self.par not in [3, 4, 5]:
            raise ValueError(f"Par must be 3, 4, or 5, got {self.par}")

        if not (1 <= self.stroke_index <= 18):  # noqa: PLR2004
            raise ValueError(
                f"Stroke index must be between 1 and 18, got {self.stroke_index}"
            )
