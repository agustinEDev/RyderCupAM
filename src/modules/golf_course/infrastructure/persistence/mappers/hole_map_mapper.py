"""
SQLAlchemy Mapper for the CourseHoleMap aggregate (BE #532).

Tabla:
- golf_course_hole_maps (una fila por campo; los hoyos, embebidos en JSONB)

Los hoyos van en JSONB y no en una tabla aparte, como los participantes de una
partida rápida: el mapa se lee y se guarda siempre entero, nunca un hoyo suelto.
La validez de cada hoyo (número 1-18, sin repetir, línea con salida) la
garantiza el dominio.
"""

from typing import Any

import sqlalchemy.types
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Table, inspect
from sqlalchemy.dialects.postgresql import JSONB

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata

from .golf_course_mapper import GolfCourseIdType, UserIdType

# ============================================================================
# TypeDecorators
# ============================================================================


def _point_to_json(point: GeoPoint) -> list[float]:
    return [point.latitude, point.longitude]


def _point_from_json(value: list[float]) -> GeoPoint:
    return GeoPoint(latitude=value[0], longitude=value[1])


class HoleMapStatusType(sqlalchemy.types.TypeDecorator[HoleMapStatus]):
    """TypeDecorator para HoleMapStatus."""

    impl = String(20)
    cache_ok = True

    def process_bind_param(self, value: HoleMapStatus | str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        # Admite también el texto, para filtrar por estado sin construir el enum
        return HoleMapStatus(value).value

    def process_result_value(self, value: str | None, dialect: Any) -> HoleMapStatus | None:
        if value is None:
            return None
        return HoleMapStatus(value)


class MappedHolesJsonType(sqlalchemy.types.TypeDecorator[tuple]):
    """
    TypeDecorator para serializar tuple[MappedHole] a/desde JSONB.

    Cada hoyo se serializa como (los puntos, `[latitud, longitud]`):
    {
        "number": 1,
        "play_line": [[lat, lon], ...],        # el primero es la salida
        "line_source": "OSM" | "MANUAL" | "PLAYER",
        "green": null | {
            "front": [lat, lon], "center": [lat, lon], "back": [lat, lon],
            "outline": [[lat, lon], ...],      # vacío si no hay contorno
            "source": "OSM" | "MANUAL" | "PLAYER"
        }
    }
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | None, dialect: Any) -> list | None:
        if value is None:
            return None
        return [
            {
                "number": hole.number,
                "play_line": [_point_to_json(p) for p in hole.play_line],
                "line_source": hole.line_source.value,
                "green": None
                if hole.green is None
                else {
                    "front": _point_to_json(hole.green.front),
                    "center": _point_to_json(hole.green.center),
                    "back": _point_to_json(hole.green.back),
                    "outline": [_point_to_json(p) for p in hole.green.outline],
                    "source": hole.green.source.value,
                },
            }
            for hole in value
        ]

    def process_result_value(self, value: list | None, dialect: Any) -> tuple | None:
        if value is None:
            return None
        return tuple(
            MappedHole(
                number=hole["number"],
                play_line=tuple(_point_from_json(p) for p in hole["play_line"]),
                line_source=PositionSource(hole["line_source"]),
                green=None
                if hole["green"] is None
                else GreenPosition(
                    front=_point_from_json(hole["green"]["front"]),
                    center=_point_from_json(hole["green"]["center"]),
                    back=_point_from_json(hole["green"]["back"]),
                    outline=tuple(_point_from_json(p) for p in hole["green"]["outline"]),
                    source=PositionSource(hole["green"]["source"]),
                ),
            )
            for hole in value
        )


# ============================================================================
# Tables
# ============================================================================

golf_course_hole_maps_table = Table(
    "golf_course_hole_maps",
    metadata,
    # El campo ES la identidad del mapa: como mucho uno por recorrido
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("holes", MappedHolesJsonType, nullable=False, comment="Hoyos del mapa (JSONB)"),
    Column(
        "osm_reference",
        String(40),
        nullable=False,
        comment="Contorno del campo en OSM: way/<id> o relation/<id>",
    ),
    Column("imported_at", DateTime, nullable=False, comment="Cuándo se importó"),
    Column(
        "status",
        HoleMapStatusType,
        nullable=False,
        comment="Revisión: PENDING_REVIEW, APPROVED o REJECTED",
    ),
    # SET NULL: borrar al admin que lo revisó no deshace la revisión
    Column(
        "reviewed_by",
        UserIdType,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin que lo revisó",
    ),
    Column("reviewed_at", DateTime, nullable=True, comment="Cuándo se revisó"),
    Column("rejection_reason", String(500), nullable=True, comment="Motivo del rechazo"),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    CheckConstraint(
        "status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
        name="ck_golf_course_hole_maps_status",
    ),
    # Un mapa revisado lleva fecha de revisión; uno pendiente, no
    CheckConstraint(
        "(status = 'PENDING_REVIEW') = (reviewed_at IS NULL)",
        name="ck_golf_course_hole_maps_review_consistency",
    ),
    # Al leer, SQLAlchemy no pasa por el dominio: la BD garantiza al menos un hoyo
    CheckConstraint(
        "jsonb_typeof(holes) = 'array' AND jsonb_array_length(holes) > 0",
        name="ck_golf_course_hole_maps_has_holes",
    ),
    # Solo un mapa rechazado lleva motivo de rechazo
    CheckConstraint(
        "rejection_reason IS NULL OR status = 'REJECTED'",
        name="ck_golf_course_hole_maps_reason_only_if_rejected",
    ),
    comment="Mapa de los hoyos de cada recorrido (posiciones de OSM o propias)",
)


# ============================================================================
# Imperative Mapping
# ============================================================================


def start_hole_map_mappers() -> None:
    """Mapea CourseHoleMap a su tabla. Idempotente."""
    if inspect(CourseHoleMap, raiseerr=False) is not None:
        return
    table = golf_course_hole_maps_table
    mapper_registry.map_imperatively(
        CourseHoleMap,
        table,
        properties={
            "_golf_course_id": table.c.golf_course_id,
            "_holes": table.c.holes,
            "_osm_reference": table.c.osm_reference,
            "_imported_at": table.c.imported_at,
            "_status": table.c.status,
            "_reviewed_by": table.c.reviewed_by,
            "_reviewed_at": table.c.reviewed_at,
            "_rejection_reason": table.c.rejection_reason,
            "_created_at": table.c.created_at,
            "_updated_at": table.c.updated_at,
        },
    )
