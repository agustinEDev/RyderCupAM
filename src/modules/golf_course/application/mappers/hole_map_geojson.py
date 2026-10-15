"""
El mapa de hoyos en GeoJSON (BE #532): lo que pinta el front tal cual.

GeoJSON pone la longitud ANTES que la latitud, al revés que el resto de la app.
"""

from typing import Any

from geojson_pydantic import Feature, FeatureCollection, LineString, Point, Polygon
from geojson_pydantic.types import Position2D

from src.modules.golf_course.application.dtos.hole_map_dtos import (
    HoleMapDTO,
    HoleMapReviewDTO,
    version_of,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.position_source import PositionSource

# Lo que pide la licencia ODbL cuando se enseñan datos de OpenStreetMap
OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"


def _xy(point: GeoPoint) -> Position2D:
    return Position2D(longitude=point.longitude, latitude=point.latitude)


def _feature(geometry: Any, hole: int, kind: str, source: PositionSource) -> Feature:
    return Feature(
        type="Feature",
        geometry=geometry,
        properties={"hole": hole, "kind": kind, "source": source.value},
    )


def _features(hole_map: CourseHoleMap) -> list[Feature]:
    features: list[Feature] = []
    for hole in hole_map.holes:
        features.append(
            _feature(
                LineString(type="LineString", coordinates=[_xy(p) for p in hole.play_line]),
                hole.number,
                "play_line",
                hole.line_source,
            )
        )
        green = hole.green
        if green is None:
            continue
        for kind, point in (
            ("green_front", green.front),
            ("green_center", green.center),
            ("green_back", green.back),
        ):
            features.append(
                _feature(
                    Point(type="Point", coordinates=_xy(point)), hole.number, kind, green.source
                )
            )
        if green.outline:
            ring = [_xy(p) for p in green.outline]
            features.append(
                _feature(
                    Polygon(type="Polygon", coordinates=[[*ring, ring[0]]]),
                    hole.number,
                    "green_outline",
                    green.source,
                )
            )
    return features


def _attribution(hole_map: CourseHoleMap) -> str | None:
    sources = {hole.line_source for hole in hole_map.holes} | {
        hole.green.source for hole in hole_map.holes if hole.green is not None
    }
    return OSM_ATTRIBUTION if PositionSource.OSM in sources else None


def _common(hole_map: CourseHoleMap) -> dict[str, Any]:
    return {
        "golf_course_id": str(hole_map.golf_course_id),
        "status": hole_map.status.value,
        "version": version_of(hole_map.imported_at),
        "attribution": _attribution(hole_map),
        "holes_needing_green": [hole.number for hole in hole_map.holes if hole.needs_green],
        "geojson": FeatureCollection(type="FeatureCollection", features=_features(hole_map)),
    }


def to_hole_map_dto(hole_map: CourseHoleMap) -> HoleMapDTO:
    """El mapa para el jugador."""
    return HoleMapDTO(**_common(hole_map))


def to_hole_map_review_dto(hole_map: CourseHoleMap) -> HoleMapReviewDTO:
    """El mapa para el admin que lo revisa."""
    return HoleMapReviewDTO(
        **_common(hole_map),
        osm_reference=hole_map.osm_reference,
        reviewed_by=str(hole_map.reviewed_by) if hole_map.reviewed_by is not None else None,
        reviewed_at=hole_map.reviewed_at,
        rejection_reason=hole_map.rejection_reason,
    )
