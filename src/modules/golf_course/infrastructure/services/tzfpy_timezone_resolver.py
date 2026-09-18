"""
Adaptador: la zona horaria de unas coordenadas, con `tzfpy`.

`tzfpy` lleva dentro las fronteras de husos del mundo en 3 MB y sin
dependencias, que es lo que la hace viable aquí: la alternativa habitual,
`timezonefinder`, arrastra numpy.
"""

import logging

from tzfpy import get_tz

from src.modules.golf_course.application.ports.timezone_resolver import ITimezoneResolver

logger = logging.getLogger(__name__)

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


class TzfpyTimezoneResolver(ITimezoneResolver):
    """Resuelve la zona horaria de un punto contra las fronteras de husos."""

    def for_coordinates(self, latitude: float | None, longitude: float | None) -> str | None:
        """La zona IANA de ese punto, o `None` si no hay punto o no se conoce."""
        if latitude is None or longitude is None:
            return None
        if not (MIN_LATITUDE <= latitude <= MAX_LATITUDE):
            return None
        if not (MIN_LONGITUDE <= longitude <= MAX_LONGITUDE):
            return None

        try:
            # `tzfpy` recibe longitud primero, y ese orden se confunde solo
            return get_tz(longitude, latitude)
        except Exception:
            # Un punto sin zona conocida no puede tumbar el alta de un campo: se
            # queda sin apertura automatica y la pantalla lo avisa
            logger.warning(
                "No se pudo resolver la zona horaria de (%s, %s)", latitude, longitude
            )
            return None
