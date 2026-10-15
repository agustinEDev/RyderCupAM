"""
GreenPosition Value Object - Dónde está el green de un hoyo.

Delante, centro y fondo son los tres puntos de los que el jugador quiere la
distancia (BE #532). El contorno sirve para dibujarlo y es opcional: el green
que marca un jugador con el dedo tiene puntos, pero no silueta.
"""

from dataclasses import dataclass

from .geo_point import GeoPoint
from .position_source import PositionSource

MIN_OUTLINE_POINTS = 3


@dataclass(frozen=True)
class GreenPosition:
    """
    El green de un hoyo.

    Business Rules:
    - Delante, centro y fondo son obligatorios.
    - El contorno, si lo hay, tiene al menos tres puntos: con menos no encierra
      ninguna superficie.
    - Lleva su propio origen, independiente del de la línea del hoyo.
    """

    front: GeoPoint
    center: GeoPoint
    back: GeoPoint
    source: PositionSource
    outline: tuple[GeoPoint, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "outline", tuple(self.outline))
        if self.outline and len(self.outline) < MIN_OUTLINE_POINTS:
            raise ValueError(
                f"Green outline needs at least {MIN_OUTLINE_POINTS} points, got {len(self.outline)}"
            )
