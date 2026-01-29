"""
Tee Entity - Salida de un campo de golf con ratings WHS.
"""

from dataclasses import dataclass

from ..value_objects.tee_category import TeeCategory


@dataclass
class Tee:
    """
    Tee (salida) de un campo de golf.

    Attributes:
        category: Categoría normalizada (AMATEUR_MALE, CHAMPIONSHIP_FEMALE, etc.)
        identifier: Identificador libre del tee (ej: "Amarillo", "Blanco", "Rojo")
        slope_rating: Slope Rating WHS (55-155, típico 113)
        course_rating: Course Rating WHS (decimal, ej: 71.5)

    WHS Formula:
        Playing Handicap = (HI * SR / 113) + (CR - Par)

    Example:
        >>> tee = Tee(
        ...     category=TeeCategory.AMATEUR_MALE,
        ...     identifier="Amarillo",
        ...     slope_rating=126,
        ...     course_rating=71.5
        ... )
    """

    category: TeeCategory
    identifier: str  # Color o nombre del tee (libre)
    slope_rating: int  # 55-155 (WHS)
    course_rating: float  # Course Rating (WHS)

    def __post_init__(self) -> None:
        """Valida los ratings WHS."""
        if not (55 <= self.slope_rating <= 155):  # noqa: PLR2004
            raise ValueError(f"Slope rating must be between 55 and 155, got {self.slope_rating}")

        if not (50.0 <= self.course_rating <= 90.0):  # noqa: PLR2004
            raise ValueError(
                f"Course rating must be between 50.0 and 90.0, got {self.course_rating}"
            )

        if not (1 <= len(self.identifier) <= 50):  # noqa: PLR2004
            raise ValueError(
                f"Tee identifier must be between 1 and 50 characters, got {len(self.identifier)}"
            )
