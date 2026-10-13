"""Un campo de una competición, con lo que hace falta para nombrarlo (FE #846)."""

from dataclasses import dataclass

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.shared.domain.value_objects.country_code import CountryCode


@dataclass(frozen=True)
class CampoDeLaCompeticion:
    """Lectura: el campo, su nombre y su país, en el orden de la competición."""

    golf_course_id: GolfCourseId
    nombre: str
    country_code: CountryCode
