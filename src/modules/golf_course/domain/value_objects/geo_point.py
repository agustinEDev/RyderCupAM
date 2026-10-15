"""
GeoPoint Value Object - Un punto sobre el terreno, en grados decimales (WGS84).

Es la pieza de la que se hacen las posiciones del mapa de un hoyo (BE #532).
"""

import math
from dataclasses import dataclass

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


@dataclass(frozen=True)
class GeoPoint:
    """
    Un punto con latitud y longitud.

    Business Rules:
    - Las dos coordenadas son números finitos, y no booleanos (True vale 1): un NaN pasa cualquier comparación
      de rango sin saltar y acabaría como distancia imposible en el campo.
    - Los rangos son los geográficos absolutos, sin acotar a un país.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if isinstance(self.latitude, bool) or isinstance(self.longitude, bool):
            raise ValueError("Point coordinates must be numbers, not booleans")
        if not (math.isfinite(self.latitude) and math.isfinite(self.longitude)):
            raise ValueError(
                f"Point coordinates must be finite numbers, got ({self.latitude}, {self.longitude})"
            )
        if not MIN_LATITUDE <= self.latitude <= MAX_LATITUDE:
            raise ValueError(f"Point latitude must be between -90 and 90, got {self.latitude}")
        if not MIN_LONGITUDE <= self.longitude <= MAX_LONGITUDE:
            raise ValueError(f"Point longitude must be between -180 and 180, got {self.longitude}")
