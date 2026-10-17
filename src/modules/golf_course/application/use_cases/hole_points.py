"""
Lo que comparten los casos de uso de muestras y líneas de los hoyos (BE #575).

El campo que ven los jugadores, su ubicación, y los puntos entre la API y el
dominio: en un solo sitio, para que muestras y líneas se validen y se lean igual.
"""

from typing import TypeGuard

from src.modules.golf_course.application.dtos.hole_sample_dtos import HoleSampleDTO, PointDTO
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint


def visible(course: GolfCourse | None) -> TypeGuard[GolfCourse]:
    """
    Un campo que ven los jugadores: aprobado. La propuesta de cambio de un campo
    (su clon) nace pendiente y se borra al aprobarla, así que nunca lo está.
    """
    return course is not None and course.approval_status.is_approved()


def location_of(course: GolfCourse) -> GeoPoint | None:
    """La ubicación del campo, o None si no la tiene."""
    location = course.location
    if location.latitude is None or location.longitude is None:
        return None
    return GeoPoint(latitude=location.latitude, longitude=location.longitude)


def to_point(point: PointDTO, error: type[Exception]) -> GeoPoint:
    """El punto de la API, o `error` si sus coordenadas son imposibles."""
    try:
        return GeoPoint(latitude=point.latitude, longitude=point.longitude)
    except ValueError as e:
        raise error("Invalid coordinates") from e


def point_dto(point: GeoPoint) -> PointDTO:
    """El punto para la API."""
    return PointDTO(latitude=point.latitude, longitude=point.longitude)


def line_dto(tee: GeoPoint, bends: tuple[GeoPoint, ...], green_center: GeoPoint) -> HoleSampleDTO:
    """Una línea completa (salida, codos y green) para la API."""
    return HoleSampleDTO(
        tee=point_dto(tee),
        bends=[point_dto(bend) for bend in bends],
        green_center=point_dto(green_center),
    )
