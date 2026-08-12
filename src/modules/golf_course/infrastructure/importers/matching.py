"""
Reconocer qué campos de la base de datos son los que trae la importación.

El identificador externo resuelve el caso normal. Lo demás existe para dos
situaciones que sí ocurren: que la federación renombre un recorrido, y que el
campo ya estuviera dado de alta a mano antes de que existiera el importador.
Ninguna coincidencia que no sea exacta se aplica sola: se propone y decide una
persona.
"""

from dataclasses import dataclass
from enum import StrEnum
from math import asin, cos, radians, sin, sqrt

from src.modules.golf_course.domain.value_objects.course_source import CourseSource

from .course_names import normalize_for_comparison
from .rfeg_mapper import MappedCourse

# Un campo de golf de 18 hoyos ocupa alrededor de un kilómetro de lado, así que
# dos recorridos del mismo club caen dentro de este radio. Por eso la cercanía
# nunca decide sola: acompaña siempre a la forma de la tarjeta.
NEARBY_METERS = 800.0

EARTH_RADIUS_METERS = 6_371_000.0


class MatchKind(StrEnum):
    """Cómo se ha reconocido un campo."""

    NEW = "NEW"
    EXACT = "EXACT"
    RENAMED = "RENAMED"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class ExistingCourse:
    """
    Lo que hace falta saber de un campo ya guardado para reconocerlo.

    Es una foto plana y no la entidad: así el emparejamiento se puede probar
    sin base de datos.
    """

    id: str
    name: str
    source: CourseSource
    external_id: str | None
    latitude: float | None
    longitude: float | None
    total_par: int
    tee_count: int


@dataclass(frozen=True)
class Match:
    """El resultado de buscar un campo de la importación entre los guardados."""

    kind: MatchKind
    existing: ExistingCourse | None = None
    reason: str = ""

    @property
    def needs_confirmation(self) -> bool:
        """
        True si la coincidencia la tiene que aprobar una persona.

        Solo el identificador externo es prueba suficiente. Todo lo demás es un
        parecido, y equivocarse significa sobrescribir un campo con los datos de
        otro.
        """
        return self.kind in (MatchKind.RENAMED, MatchKind.MANUAL)


def distance_in_meters(
    first_latitude: float, first_longitude: float, second_latitude: float, second_longitude: float
) -> float:
    """Distancia entre dos puntos sobre la superficie terrestre, en metros."""
    lat1, lon1, lat2, lon2 = map(
        radians, (first_latitude, first_longitude, second_latitude, second_longitude)
    )
    half_chord = (
        sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(half_chord))


def _club_prefix(external_id: str) -> str:
    """Devuelve el tramo del identificador que señala al club."""
    return external_id.split(":", 1)[0]


def _has_same_shape(course: MappedCourse, existing: ExistingCourse) -> bool:
    """
    True si los dos describen un campo con la misma forma.

    Se comparan el par total y el número de salidas, que es lo que distingue
    dos recorridos del mismo club: comparten ubicación y club, así que sin esto
    un pitch & putt podría emparejarse con el campo grande de al lado.
    """
    total_par = sum(hole.par for hole in course.request.holes)
    return total_par == existing.total_par and len(course.request.tees) == existing.tee_count


def _is_nearby(course: MappedCourse, existing: ExistingCourse) -> bool:
    """True si el campo guardado está lo bastante cerca del que se importa."""
    location = course.request.location
    if location is None or location.latitude is None or location.longitude is None:
        return False
    if existing.latitude is None or existing.longitude is None:
        return False
    return (
        distance_in_meters(
            location.latitude, location.longitude, existing.latitude, existing.longitude
        )
        <= NEARBY_METERS
    )


def find_match(course: MappedCourse, existing_courses: list[ExistingCourse]) -> Match:
    """
    Busca el campo guardado que corresponde al que se está importando.

    El orden va de la prueba más fuerte a la más débil:

    1. Mismo identificador externo: es el mismo recorrido de la misma fuente.
    2. Mismo club y misma forma de tarjeta, pero identificador distinto: la
       federación lo ha renombrado. Se propone, no se aplica.
    3. Un campo dado de alta a mano que coincide en nombre, o que está al lado
       con la misma tarjeta. También se propone.

    Cualquier caso ambiguo, con más de un candidato, se trata como campo nuevo
    y se informa: duplicar es reparable, sobrescribir el campo equivocado no.

    Args:
        course: Campo que trae la importación
        existing_courses: Campos ya guardados

    Returns:
        El resultado del emparejamiento
    """
    external_id = course.provenance.external_id
    if external_id is None:
        return Match(kind=MatchKind.NEW, reason="the imported course has no external id")

    for existing in existing_courses:
        if existing.source is course.provenance.source and existing.external_id == external_id:
            return Match(kind=MatchKind.EXACT, existing=existing, reason="same external id")

    renamed = [
        existing
        for existing in existing_courses
        if existing.source is course.provenance.source
        and existing.external_id is not None
        and _club_prefix(existing.external_id) == _club_prefix(external_id)
        and _has_same_shape(course, existing)
    ]
    if len(renamed) == 1:
        return Match(
            kind=MatchKind.RENAMED,
            existing=renamed[0],
            reason=(
                f"same club and same scorecard shape as '{renamed[0].name}', "
                "which suggests the federation renamed it"
            ),
        )

    imported_name = normalize_for_comparison(course.request.name)
    manual = [
        existing
        for existing in existing_courses
        if existing.source is CourseSource.MANUAL
        and (
            normalize_for_comparison(existing.name) == imported_name
            or (_is_nearby(course, existing) and _has_same_shape(course, existing))
        )
    ]
    if len(manual) == 1:
        return Match(
            kind=MatchKind.MANUAL,
            existing=manual[0],
            reason=(
                f"'{manual[0].name}' was created by hand and looks like the same course "
                "(matching name, or same scorecard right next to it)"
            ),
        )
    if len(manual) > 1:
        return Match(
            kind=MatchKind.NEW,
            reason=f"{len(manual)} hand-created courses look alike, too ambiguous to merge",
        )

    return Match(kind=MatchKind.NEW, reason="no course in the database matches it")
