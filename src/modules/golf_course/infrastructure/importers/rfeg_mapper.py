"""
Traduce los recorridos publicados por la RFEG a las peticiones del backend.

Un recorrido de la federación es un campo de golf de la aplicación. El mapeo
va por los DTOs y no escribe en la base de datos: así los 802 recorridos pasan
por las mismas invariantes que un alta hecha a mano.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    HoleDTO,
    LocationDTO,
    RequestGolfCourseRequestDTO,
    TeeDTO,
)
from src.modules.golf_course.domain.value_objects.course_provenance import CourseProvenance
from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor

from .course_names import build_club_course_names, normalize_for_comparison, prettify_place

# Los nueve colores que usan los campos federados españoles. La lista se
# comprobó sobre los 802 recorridos: no aparece ninguno más, así que un color
# desconocido significa que la fuente ha cambiado y merece parar.
COLOR_BY_SPANISH_NAME: dict[str, TeeColor] = {
    "ROJAS": TeeColor.RED,
    "AMARILLAS": TeeColor.YELLOW,
    "AZULES": TeeColor.BLUE,
    "BLANCAS": TeeColor.WHITE,
    "VERDES": TeeColor.GREEN,
    "NARANJAS": TeeColor.ORANGE,
    "NEGRAS": TeeColor.BLACK,
    "ROSAS": TeeColor.PINK,
    "DORADAS": TeeColor.GOLD,
}

GENDER_BY_SOURCE_CODE = {"M": "MALE", "F": "FEMALE"}

# El tipo se decide por el par total, que es como los distingue el propio
# reglamento. Los rangos son los que valida el agregado.
PAR_RANGES: list[tuple[CourseType, int, int]] = [
    (CourseType.PITCH_AND_PUTT, 54, 60),
    (CourseType.EXECUTIVE, 61, 65),
    (CourseType.STANDARD_18, 66, 76),
]

HOLES_PER_ROUND = 18
HALF_ROUND = 9
SPAIN = "ES"


class RfegMappingError(ValueError):
    """Un recorrido que no se puede traducir a un campo de la aplicación."""


@dataclass(frozen=True)
class MappedCourse:
    """Un recorrido de la RFEG ya traducido, listo para el caso de uso."""

    request: RequestGolfCourseRequestDTO
    provenance: CourseProvenance
    physical_holes: int
    club_name: str
    source_course_name: str

    @property
    def name(self) -> str:
        """Nombre con el que se dará de alta el campo."""
        return self.request.name


def build_external_id(club: dict[str, Any], source_course_name: str) -> str:
    """
    Compone el identificador con el que se reconoce un campo ya importado.

    Se usa el id del club en la federación y el nombre del recorrido **tal como
    lo publica la fuente**, normalizado. No se usa el nombre bonito: ese
    depende de nuestras tablas de tildes y capitalización, y cambiarlas
    convertiría todos los campos en desconocidos en la siguiente importación.

    Tampoco sirve el `way_id` de la RFEG: identifica cada salida, no el
    recorrido. En 800 de los 802 recorridos hay un `way_id` distinto por barra.

    Args:
        club: Club tal como viene en el dataset
        source_course_name: Nombre del recorrido en la fuente

    Returns:
        Identificador estable, del estilo '915:GOLF DE DERIO - P&P'
    """
    return f"{club['rfeg_id']}:{normalize_for_comparison(source_course_name)}"


def detect_course_type(total_par: int) -> CourseType:
    """
    Decide el tipo de campo a partir del par total.

    Raises:
        RfegMappingError: Si el par no cae en ningún rango conocido
    """
    for course_type, minimum, maximum in PAR_RANGES:
        if minimum <= total_par <= maximum:
            return course_type
    raise RfegMappingError(f"Total par {total_par} does not match any course type")


def detect_physical_holes(club: dict[str, Any], reference_card: list[dict[str, Any]]) -> int:
    """
    Decide si el recorrido es de nueve hoyos sobre el terreno.

    Se combinan dos señales porque ninguna basta sola:

    - Lo que la federación declara del club. Deja fuera 148 recorridos, que son
      los pitch & putt y circuitos cortos anexos a campos de 18 o 27 hoyos.
    - Que la vuelta de ida y la de vuelta sean idénticas en par y en metros.
      Deja fuera 83 campos de nueve reales, los que juegan la segunda vuelta
      desde otras barras.

    Juntas marcan 342 de los 802 recorridos.

    Args:
        club: Club tal como viene en el dataset
        reference_card: Tarjeta de la primera salida, 18 hoyos

    Returns:
        9 o 18
    """
    if club.get("total_holes") == HALF_ROUND:
        return HALF_ROUND

    front = reference_card[:HALF_ROUND]
    back = reference_card[HALF_ROUND:]
    same_pars = [hole["par"] for hole in front] == [hole["par"] for hole in back]
    same_meters = [hole.get("meters") for hole in front] == [hole.get("meters") for hole in back]
    if same_pars and same_meters:
        return HALF_ROUND

    return HOLES_PER_ROUND


def _map_holes(source_holes: list[dict[str, Any]]) -> list[HoleDTO]:
    """Traduce la tarjeta de una salida."""
    if len(source_holes) != HOLES_PER_ROUND:
        raise RfegMappingError(f"A tee must have {HOLES_PER_ROUND} holes, got {len(source_holes)}")
    return [
        HoleDTO(
            hole_number=hole["number"],
            par=hole["par"],
            stroke_index=hole["stroke_index"],
            meters=hole.get("meters"),
        )
        for hole in sorted(source_holes, key=lambda hole: hole["number"])
    ]


def _map_tee(source_tee: dict[str, Any]) -> TeeDTO:
    """Traduce una salida con su tarjeta."""
    color_name = (source_tee.get("color") or "").upper()
    color = COLOR_BY_SPANISH_NAME.get(color_name)
    if color is None:
        raise RfegMappingError(f"Unknown tee colour '{source_tee.get('color')}'")

    gender_code = source_tee.get("gender")
    gender = GENDER_BY_SOURCE_CODE.get(gender_code or "")
    if gender is None:
        raise RfegMappingError(f"Unknown tee gender '{gender_code}'")

    return TeeDTO(
        color=color,
        tee_gender=gender,
        identifier=None,
        course_rating=source_tee["course_rating"],
        slope_rating=source_tee["slope_rating"],
        holes=_map_holes(source_tee.get("holes") or []),
    )


def _map_location(club: dict[str, Any]) -> LocationDTO | None:
    """
    Traduce la ubicación del club.

    Las coordenadas van juntas o no van, así que si faltara una se descartan
    ambas: 11 de los 442 clubes no las publican.
    """
    latitude = club.get("latitude")
    longitude = club.get("longitude")
    has_coordinates = latitude is not None and longitude is not None

    location = LocationDTO(
        latitude=latitude if has_coordinates else None,
        longitude=longitude if has_coordinates else None,
        address=club.get("address"),
        city=prettify_place(club.get("place")),
        province=prettify_place(club.get("province")),
    )
    if location.model_dump(exclude_none=True):
        return location
    return None


def map_club(club: dict[str, Any], imported_at: datetime) -> list[MappedCourse]:
    """
    Traduce todos los recorridos de un club.

    Va por club y no por recorrido porque el nombre de uno depende de los
    demás: dos recorridos del mismo club pueden colisionar al abreviarlos.

    Es la variante estricta: el primer recorrido ilegible corta la traducción
    del club entero. La importación usa map_club_courses, que aísla el fallo.

    Args:
        club: Club tal como viene en el dataset
        imported_at: Momento de la importación, igual para todo el lote

    Returns:
        Un MappedCourse por recorrido

    Raises:
        RfegMappingError: Si algún recorrido no se puede traducir
    """
    courses, names, location = _prepare_club(club)
    return [
        _map_course(club, course, name, location, imported_at)
        for course, name in zip(courses, names, strict=True)
    ]


def map_club_courses(
    club: dict[str, Any], imported_at: datetime
) -> tuple[list[MappedCourse], list[str]]:
    """
    Traduce los recorridos de un club sin que uno ilegible arrastre a los demás.

    A diferencia de map_club, aquí cada recorrido se traduce por separado: si
    uno falla se anota y se sigue con el resto. Un club con dos recorridos no
    debe perder el bueno por culpa del malo.

    Lo previo al bucle (los nombres y la ubicación) sí es del club entero y no
    se puede aislar, así que si eso falla la excepción sale hacia fuera.

    Se captura `ValueError` y no solo `RfegMappingError` porque los DTO son de
    Pydantic y su `ValidationError` es un `ValueError`: un rating fuera de
    rango tumbaría la importación entera si no se recogiera aquí.
    `RfegMappingError` también hereda de `ValueError`, así que queda cubierto.

    Args:
        club: Club tal como viene en el dataset
        imported_at: Momento de la importación, igual para todo el lote

    Returns:
        Los recorridos traducidos y la descripción de los que no se pudieron

    Raises:
        RfegMappingError: Si no se puede preparar el club
    """
    courses, names, location = _prepare_club(club)

    mapped: list[MappedCourse] = []
    problems: list[str] = []
    for course, name in zip(courses, names, strict=True):
        try:
            mapped.append(_map_course(club, course, name, location, imported_at))
        except (ValueError, KeyError, TypeError) as error:
            source_name = course.get("name", "?") if isinstance(course, dict) else "?"
            problems.append(f"{club.get('name', '?')} / {source_name}: {error}")

    return mapped, problems


def _prepare_club(
    club: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], LocationDTO | None]:
    """
    Resuelve lo que es común a todos los recorridos de un club.

    Los nombres se calculan de golpe porque el de un recorrido depende de los
    demás: dos del mismo club pueden colisionar al abreviarlos.
    """
    courses = club.get("courses") or []
    names = build_club_course_names(club["name"], [course["name"] for course in courses])
    return courses, names, _map_location(club)


def _map_course(
    club: dict[str, Any],
    course: dict[str, Any],
    name: str,
    location: LocationDTO | None,
    imported_at: datetime,
) -> MappedCourse:
    """
    Traduce un único recorrido, con el nombre y la ubicación ya resueltos.

    Raises:
        RfegMappingError: Si el recorrido no se puede traducir
    """
    source_tees = course.get("tees") or []
    if not source_tees:
        raise RfegMappingError(f"Course '{course['name']}' has no tees")

    tees = [_map_tee(source_tee) for source_tee in source_tees]
    reference_card = sorted(source_tees[0].get("holes") or [], key=lambda hole: hole["number"])
    holes = _map_holes(reference_card)
    course_type = detect_course_type(sum(hole.par for hole in holes))

    request = RequestGolfCourseRequestDTO(
        name=name,
        country_code=SPAIN,
        course_type=course_type,
        tees=tees,
        holes=holes,
        location=location,
    )
    return MappedCourse(
        request=request,
        provenance=CourseProvenance(
            source=CourseSource.RFEG,
            external_id=build_external_id(club, course["name"]),
            imported_at=imported_at,
        ),
        physical_holes=detect_physical_holes(club, reference_card),
        club_name=club["name"],
        source_course_name=course["name"],
    )
