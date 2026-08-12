"""
CourseLocation Value Object - Dónde está físicamente un campo de golf.

Existe para poder proponer campos cercanos a la ubicación del dispositivo. Todo
es opcional: los campos dados de alta a mano pueden no tener coordenadas, y las
federaciones no siempre las publican (11 de los 442 clubes españoles no las
traen).
"""

from dataclasses import dataclass

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

MAX_ADDRESS_LENGTH = 300
MAX_CITY_LENGTH = 100
MAX_PROVINCE_LENGTH = 100


@dataclass(frozen=True)
class CourseLocation:
    """
    Ubicación de un campo de golf.

    Business Rules:
    - Latitud y longitud van juntas: media coordenada no sitúa nada en un mapa,
      y una búsqueda por cercanía que aceptara solo una devolvería resultados
      arbitrarios.
    - Los rangos son los geográficos absolutos; no se acotan a España porque el
      modelo admite campos de cualquier país.
    - Las cadenas vacías se normalizan a None: un texto en blanco no es un dato,
      y guardarlo obligaría a todos los consumidores a distinguir '' de None.
    """

    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None

    def __post_init__(self) -> None:
        for field_name, max_length in (
            ("address", MAX_ADDRESS_LENGTH),
            ("city", MAX_CITY_LENGTH),
            ("province", MAX_PROVINCE_LENGTH),
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            cleaned = value.strip()
            object.__setattr__(self, field_name, cleaned or None)
            if cleaned and len(cleaned) > max_length:
                raise ValueError(
                    f"Course location {field_name} must be at most {max_length} characters, "
                    f"got {len(cleaned)}"
                )

        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "Course location needs both latitude and longitude, or neither. "
                f"Got latitude={self.latitude}, longitude={self.longitude}"
            )

        if self.latitude is not None and not (MIN_LATITUDE <= self.latitude <= MAX_LATITUDE):
            raise ValueError(
                f"Latitude must be between {MIN_LATITUDE} and {MAX_LATITUDE}, got {self.latitude}"
            )

        if self.longitude is not None and not (MIN_LONGITUDE <= self.longitude <= MAX_LONGITUDE):
            raise ValueError(
                f"Longitude must be between {MIN_LONGITUDE} and {MAX_LONGITUDE}, "
                f"got {self.longitude}"
            )

    @property
    def has_coordinates(self) -> bool:
        """True si el campo se puede situar en un mapa."""
        return self.latitude is not None and self.longitude is not None

    @property
    def is_empty(self) -> bool:
        """True si no aporta ningún dato de ubicación."""
        return not any((self.latitude, self.longitude, self.address, self.city, self.province))
