"""
Geometría sintética para los tests del importador de OSM (BE #532).

Todo se dibuja en metros alrededor de un origen (x hacia el este, y hacia el
norte) y se traduce a latitud/longitud, para que cada caso diga sus distancias
sin depender de un campo real.
"""

import math

from src.modules.golf_course.infrastructure.osm.overpass_client import (
    OsmArea,
    OsmRelation,
    OsmWay,
)

ORIGEN_LAT = 36.28
ORIGEN_LON = -5.33
METROS_POR_GRADO_LAT = 111_320.0
METROS_POR_GRADO_LON = METROS_POR_GRADO_LAT * math.cos(math.radians(ORIGEN_LAT))


def pt(x: float, y: float) -> tuple[float, float]:
    """(latitud, longitud) del punto a x metros al este e y al norte del origen."""
    return (ORIGEN_LAT + y / METROS_POR_GRADO_LAT, ORIGEN_LON + x / METROS_POR_GRADO_LON)


def metros(lat: float, lon: float) -> tuple[float, float]:
    """Lo contrario de pt: (x, y) en metros desde el origen."""
    return ((lon - ORIGEN_LON) * METROS_POR_GRADO_LON, (lat - ORIGEN_LAT) * METROS_POR_GRADO_LAT)


def cuadrado(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    """Anillo cerrado de un rectángulo, como lo da OSM (el último punto repite el primero)."""
    return (pt(x0, y0), pt(x1, y0), pt(x1, y1), pt(x0, y1), pt(x0, y0))


def circulo(cx: float, cy: float, radio: float, puntos: int) -> tuple[tuple[float, float], ...]:
    anillo = [
        pt(
            cx + radio * math.cos(2 * math.pi * i / puntos),
            cy + radio * math.sin(2 * math.pi * i / puntos),
        )
        for i in range(puntos)
    ]
    return (*anillo, anillo[0])


def campo(way_id: int = 1, anillo=None) -> OsmWay:
    return OsmWay(
        id=way_id,
        tags={"leisure": "golf_course"},
        points=anillo if anillo is not None else cuadrado(0, 0, 1000, 1000),
    )


def hoyo(way_id: int, ref: str | None, *puntos_m: tuple[float, float], par=None, handicap=None):
    tags = {"golf": "hole"}
    if ref is not None:
        tags["ref"] = ref
    if par is not None:
        tags["par"] = par
    if handicap is not None:
        tags["handicap"] = handicap
    return OsmWay(id=way_id, tags=tags, points=tuple(pt(x, y) for x, y in puntos_m))


def green(way_id: int, cx: float, cy: float, lado: float = 20) -> OsmWay:
    mitad = lado / 2
    return OsmWay(
        id=way_id,
        tags={"golf": "green"},
        points=cuadrado(cx - mitad, cy - mitad, cx + mitad, cy + mitad),
    )


def zona(cursos=(), relaciones: tuple[OsmRelation, ...] = (), hoyos=(), greens=()) -> OsmArea:
    return OsmArea(
        course_ways=tuple(cursos),
        course_relations=tuple(relaciones),
        holes=tuple(hoyos),
        greens=tuple(greens),
    )
