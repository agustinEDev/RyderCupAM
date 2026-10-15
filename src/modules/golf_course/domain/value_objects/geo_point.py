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
EARTH_RADIUS_M = 6_371_000.0  # el mismo que el importador de campos


@dataclass(frozen=True)
class GeoPoint:
    """
    Un punto con latitud y longitud.

    Business Rules:
    - Las dos coordenadas son números finitos: ni texto, ni booleanos (True vale
      1), ni NaN, que pasa cualquier comparación de rango sin saltar y acabaría
      como distancia imposible en el campo.
    - Los rangos son los geográficos absolutos, sin acotar a un país.
    - Es también la regla de las coordenadas de la ubicación de un campo
      (CourseLocation), para que no haya dos validaciones distintas.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        for value in (self.latitude, self.longitude):
            # Un texto o un None darían TypeError (un 500) en vez de un dato inválido
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"Point coordinates must be numbers, got {value!r}")
        if not (math.isfinite(self.latitude) and math.isfinite(self.longitude)):
            raise ValueError(
                f"Point coordinates must be finite numbers, got ({self.latitude}, {self.longitude})"
            )
        if not MIN_LATITUDE <= self.latitude <= MAX_LATITUDE:
            raise ValueError(
                f"Latitude must be between {MIN_LATITUDE} and {MAX_LATITUDE}, got {self.latitude}"
            )
        if not MIN_LONGITUDE <= self.longitude <= MAX_LONGITUDE:
            raise ValueError(
                f"Longitude must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}, "
                f"got {self.longitude}"
            )

    def distance_to(self, other: "GeoPoint") -> float:
        """Distancia sobre la superficie terrestre hasta otro punto, en metros (haversine)."""
        lat1, lon1, lat2, lon2 = map(
            math.radians, (self.latitude, self.longitude, other.latitude, other.longitude)
        )
        half_chord = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        # Con puntos casi opuestos el redondeo pasa de 1 (1 + 2e-16); la raíz lo
        # devuelve a 1, pero el tope deja asin a salvo sin depender de eso
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, half_chord)))
