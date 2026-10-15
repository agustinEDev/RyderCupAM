"""
MappedHole Value Object - Un hoyo sobre el mapa: su línea de juego y su green.

La línea va de la salida al green pasando por los codos del hoyo (doglegs), como
la dibuja OpenStreetMap; su primer punto es la salida (BE #532). Sin salida no
hay hoyo en el mapa. El green puede faltar: entonces queda pendiente de que un
jugador lo marque.
"""

from dataclasses import dataclass

from .geo_point import GeoPoint
from .green_position import GreenPosition
from .position_source import PositionSource

MIN_HOLE_NUMBER = 1
MAX_HOLE_NUMBER = 18
MIN_PLAY_LINE_POINTS = 2


@dataclass(frozen=True)
class MappedHole:
    """
    Un hoyo del mapa de un recorrido.

    Business Rules:
    - Número entero de 1 a 18.
    - La línea de juego tiene al menos dos puntos; el primero es la salida.
    - El green es opcional («pendiente de marcar»).
    - La línea y el green guardan cada uno su origen.
    """

    number: int
    play_line: tuple[GeoPoint, ...]
    line_source: PositionSource
    green: GreenPosition | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "play_line", tuple(self.play_line))
        # bool es un int en Python; un 3.0 o un True acabarían tal cual en el JSONB
        if not isinstance(self.number, int) or isinstance(self.number, bool):
            raise ValueError(f"Hole number must be an integer, got {self.number!r}")
        # Un tipo equivocado reventaría al guardar (un 500); aquí es un dato inválido
        if not isinstance(self.line_source, PositionSource):
            raise ValueError(
                f"MappedHole line_source must be a PositionSource, got {self.line_source!r}"
            )
        if not all(isinstance(point, GeoPoint) for point in self.play_line):
            raise ValueError("MappedHole play line must be made of GeoPoints")
        if self.green is not None and not isinstance(self.green, GreenPosition):
            raise ValueError(f"MappedHole green must be a GreenPosition, got {self.green!r}")
        if not MIN_HOLE_NUMBER <= self.number <= MAX_HOLE_NUMBER:
            raise ValueError(f"Hole number must be between 1 and 18, got {self.number}")
        if len(self.play_line) < MIN_PLAY_LINE_POINTS:
            raise ValueError(
                f"Hole play line needs at least {MIN_PLAY_LINE_POINTS} points "
                f"(the tee and somewhere to play to), got {len(self.play_line)}"
            )

    @property
    def tee(self) -> GeoPoint:
        """La salida: el primer punto de la línea de juego."""
        return self.play_line[0]

    @property
    def needs_green(self) -> bool:
        """True si al hoyo le falta el green y hay que pedir que lo marquen."""
        return self.green is None
