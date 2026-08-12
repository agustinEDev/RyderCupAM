"""
Tee Entity - Salida de un campo de golf con ratings WHS y su tarjeta de hoyos.
"""

from dataclasses import dataclass, field

from src.shared.domain.value_objects.gender import Gender

from ..value_objects.tee_color import TeeColor
from .hole import Hole

# Rangos absolutos, unión de los de todos los tipos de campo. El rango estricto
# que corresponde a cada tipo lo valida GolfCourse, que es quien conoce su
# course_type. Aquí solo se descarta lo que no puede ser válido en ningún caso.
MIN_SLOPE_RATING = 40
MAX_SLOPE_RATING = 160
MIN_COURSE_RATING = 45.0
MAX_COURSE_RATING = 90.0
MAX_IDENTIFIER_LENGTH = 50
HOLES_PER_ROUND = 18


@dataclass
class Tee:
    """
    Tee (salida) de un campo de golf, con su tarjeta completa.

    Cada salida lleva sus propios hoyos porque el par, el índice de dificultad
    y la distancia dependen de la barra desde la que se juega.

    Una salida se identifica por su color y su género. No se clasifica por
    dificultad: las federaciones no publican tal cosa, y el reparto de colores
    varía entre campos y entre países. Lo que distingue a una salida de otra es
    dónde están las barras, y eso es lo que ve el jugador.

    Attributes:
        gender: Género del tee (MALE/FEMALE/None). Nullable.
        color: Color de las barras. OTHER cubre las salidas cuyo nombre no es un
            color, como las "Championship" británicas o las combinadas
            estadounidenses ("Gold/White"), que van con identificador propio.
        slope_rating: Slope Rating WHS (típico 113)
        course_rating: Course Rating WHS (decimal, ej: 71.5)
        holes: Los 18 hoyos tal y como se juegan desde esta salida
        identifier: Nombre libre opcional, para matices como "azules cortas"

    WHS Formula:
        Playing Handicap = (HI * SR / 113) + (CR - Par)

    Example:
        >>> tee = Tee(
        ...     gender=Gender.MALE,
        ...     color=TeeColor.YELLOW,
        ...     slope_rating=126,
        ...     course_rating=71.5,
        ...     holes=[...],
        ... )
    """

    gender: Gender | None  # MALE, FEMALE, or None (gender-neutral)
    slope_rating: int
    course_rating: float
    color: TeeColor = TeeColor.OTHER
    holes: list[Hole] = field(default_factory=list)
    identifier: str | None = None

    def __post_init__(self) -> None:
        """Valida los ratings WHS y la tarjeta de hoyos."""
        if self.color is TeeColor.OTHER and not self.identifier:
            raise ValueError("A tee with color OTHER must have an identifier")

        if not (MIN_SLOPE_RATING <= self.slope_rating <= MAX_SLOPE_RATING):
            raise ValueError(
                f"Slope rating must be between {MIN_SLOPE_RATING} and "
                f"{MAX_SLOPE_RATING}, got {self.slope_rating}"
            )

        if not (MIN_COURSE_RATING <= self.course_rating <= MAX_COURSE_RATING):
            raise ValueError(
                f"Course rating must be between {MIN_COURSE_RATING} and "
                f"{MAX_COURSE_RATING}, got {self.course_rating}"
            )

        if self.identifier is not None and not (1 <= len(self.identifier) <= MAX_IDENTIFIER_LENGTH):
            raise ValueError(
                f"Tee identifier must be between 1 and {MAX_IDENTIFIER_LENGTH} "
                f"characters, got {len(self.identifier)}"
            )

        if self.holes:
            self._validate_holes()

    def _validate_holes(self) -> None:
        """La tarjeta debe tener los 18 hoyos, sin repetir número ni índice."""
        if len(self.holes) != HOLES_PER_ROUND:
            raise ValueError(f"A tee must have {HOLES_PER_ROUND} holes, got {len(self.holes)}")

        numbers = sorted(hole.number for hole in self.holes)
        if numbers != list(range(1, HOLES_PER_ROUND + 1)):
            raise ValueError("Hole numbers must be 1..18 without duplicates")

        stroke_indices = sorted(hole.stroke_index for hole in self.holes)
        if stroke_indices != list(range(1, HOLES_PER_ROUND + 1)):
            raise ValueError("Stroke indices must be 1..18 without duplicates")

    @property
    def par_total(self) -> int:
        """Par total de la vuelta desde esta salida."""
        return sum(hole.par for hole in self.holes)

    @property
    def meters_total(self) -> int | None:
        """Distancia total desde esta salida, o None si falta algún hoyo."""
        if not self.holes or any(hole.meters is None for hole in self.holes):
            return None
        return sum(hole.meters for hole in self.holes if hole.meters is not None)

    @property
    def display_name(self) -> str:
        """Nombre para mostrar: el identificador libre si lo hay, si no el color."""
        return self.identifier or str(self.color)

    @property
    def unique_key(self) -> tuple[str, str | None]:
        """
        Clave que identifica la salida dentro de un campo.

        Normalmente basta el color, que es lo que distingue físicamente una
        salida de otra. Cuando el color es OTHER —el cajón de sastre para
        salidas cuyo nombre no es un color— se usa el identificador, porque
        OTHER puede repetirse legítimamente en un mismo campo.
        """
        gender_value = self.gender.value if self.gender else None
        if self.color is TeeColor.OTHER:
            return (f"identifier:{self.identifier}", gender_value)
        return (f"color:{self.color.value}", gender_value)
