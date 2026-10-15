"""
Emparejado de un recorrido con lo que hay en OpenStreetMap (BE #532).

De la zona que devuelve Overpass saca el mapa de hoyos de UN campo:

1. El contorno: el que contiene nuestra coordenada o, si ninguno, el más cercano
   a menos de 1 km (la coordenada suele ser la casa club, a veces fuera).
2. Los hoyos de dentro de ese contorno, validados contra nuestra tarjeta: número
   de 1 a los hoyos del campo, mismo par; los números repetidos (dos recorridos
   del club en un contorno) se deciden por el hándicap.
3. Cada hoyo con la salida primero (si la línea viene al revés, se gira) y el
   green más cercano a su final, a menos de 60 m: centro en su centro, y delante
   y fondo donde la recta de llegada (el último tramo, para los doglegs) corta
   su borde.

La geometría se hace en metros, con una proyección local centrada en nuestro
campo: en 2,5 km la distorsión es despreciable.
"""

import math
from collections import Counter
from collections.abc import Sequence

from shapely import LineString, MultiPolygon, Point, Polygon, make_valid
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    DiscardReason,
    OsmHoleMapCandidate,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource

from .overpass_client import OsmArea, OsmRelation, OsmWay

MAX_OUTLINE_DISTANCE_M = 1000.0
# Un hoyo cuyo punto medio cae a esta distancia del borde sigue siendo del campo:
# los contornos de OSM no siempre llegan al tee más atrasado
HOLE_INSIDE_MARGIN_M = 20.0
MAX_GREEN_DISTANCE_M = 60.0
OUTLINE_TOLERANCE_M = 0.5
MAX_OUTLINE_POINTS = 64
DECIMALS = 7  # 1 cm
MIN_HOLE_NUMBER = 1
MAX_HOLE_NUMBER = 18
# Un anillo cerrado necesita 4 puntos (el último repite el primero); una línea, 2;
# un contorno sin el punto de cierre, 3
MIN_RING_POINTS = 4
MIN_LINE_POINTS = 2
MIN_OUTLINE_POINTS = 3


class _Projection:
    """Latitud/longitud ↔ metros (x al este, y al norte) alrededor de un origen."""

    def __init__(self, latitude: float, longitude: float) -> None:
        phi = math.radians(latitude)
        self._lat0 = latitude
        self._lon0 = longitude
        # Metros por grado a esa latitud (elipsoide WGS84)
        self._ky = 111_132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
        self._kx = 111_412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)

    def xy(self, point: tuple[float, float]) -> tuple[float, float]:
        lat, lon = point
        return ((lon - self._lon0) * self._kx, (lat - self._lat0) * self._ky)

    def geo(self, x: float, y: float) -> GeoPoint:
        return GeoPoint(
            latitude=round(self._lat0 + y / self._ky, DECIMALS),
            longitude=round(self._lon0 + x / self._kx, DECIMALS),
        )


def _area(points: Sequence[tuple[float, float]]) -> Polygon | MultiPolygon | None:
    """
    La superficie que encierra un anillo cerrado, reparada si se corta a sí misma.

    `make_valid` y no `buffer(0)`: un contorno dibujado en ocho se queda con sus
    dos mitades, mientras que `buffer(0)` tira una y con ella sus hoyos.
    """
    if len(points) < MIN_RING_POINTS or points[0] != points[-1]:
        return None
    shape = Polygon(points)
    if not shape.is_valid:
        repaired = make_valid(shape)
        parts = [
            g
            for g in getattr(repaired, "geoms", [repaired])
            if isinstance(g, Polygon | MultiPolygon)
        ]
        if not parts:
            return None
        shape = unary_union(parts)
    return shape if isinstance(shape, Polygon | MultiPolygon) and not shape.is_empty else None


def _green_polygon(points: Sequence[tuple[float, float]]) -> Polygon | None:
    """El green como un solo polígono: si al repararlo sale en trozos, el mayor."""
    shape = _area(points)
    if isinstance(shape, MultiPolygon):
        return max(shape.geoms, key=lambda g: g.area)
    return shape


def _relation_shape(relation: OsmRelation, proj: _Projection) -> BaseGeometry | None:
    """Monta el multipolígono de una relación a partir de sus trozos de anillo."""

    def rings(pieces):
        lines = [
            LineString([proj.xy(p) for p in piece])
            for piece in pieces
            if len(piece) >= MIN_LINE_POINTS
        ]
        return unary_union(list(polygonize(unary_union(lines)))) if lines else None

    outer = rings(relation.outer)
    if outer is None or outer.is_empty:
        return None
    inner = rings(relation.inner)
    return outer.difference(inner) if inner is not None and not inner.is_empty else outer


def _outlines(area: OsmArea, proj: _Projection) -> list[tuple[str, BaseGeometry]]:
    shapes: list[tuple[str, BaseGeometry]] = []
    for way in area.course_ways:
        shape = _area([proj.xy(p) for p in way.points])
        if shape is not None:
            shapes.append((f"way/{way.id}", shape))
    for relation in area.course_relations:
        shape = _relation_shape(relation, proj)
        if shape is not None:
            shapes.append((f"relation/{relation.id}", shape))
    return shapes


def _choose_outline(
    shapes: list[tuple[str, BaseGeometry]],
) -> tuple[str, BaseGeometry] | None:
    origin = Point(0, 0)
    containing = [s for s in shapes if s[1].contains(origin)]
    if containing:
        # Un contorno dentro de otro (un recorrido dentro del club): el más ajustado
        return min(containing, key=lambda s: s[1].area)
    near = [s for s in shapes if s[1].distance(origin) <= MAX_OUTLINE_DISTANCE_M]
    return min(near, key=lambda s: s[1].distance(origin)) if near else None


def _int_tag(way: OsmWay, key: str) -> int | None:
    # isdecimal + isascii: «²» o los dígitos arábigos pasan isdigit(), pero int()
    # revienta con ellos
    value = (way.tags.get(key) or "").strip()
    return int(value) if value.isascii() and value.isdecimal() else None


def _simplified_outline(polygon: Polygon) -> list[tuple[float, float]]:
    """
    El contorno con 64 puntos como mucho, deformándolo lo menos posible.

    Primero se simplifica a 0,5 m; si aun así pasa de 64 puntos (un borde muy
    dentado), se va aflojando la tolerancia hasta que quepa.
    """
    tolerance = OUTLINE_TOLERANCE_M
    while True:
        simplified = polygon.simplify(tolerance, preserve_topology=True)
        if not isinstance(simplified, Polygon) or simplified.is_empty:
            return []
        ring = list(simplified.exterior.coords)[:-1]  # sin repetir el punto de cierre
        if len(ring) <= MAX_OUTLINE_POINTS:
            return ring if len(ring) >= MIN_OUTLINE_POINTS else []
        tolerance *= 1.5


def _green_position(
    polygon: Polygon, line: list[tuple[float, float]], proj: _Projection
) -> GreenPosition:
    center = polygon.centroid
    if not polygon.contains(center):  # un green en forma de media luna
        center = polygon.representative_point()
    (x1, y1), (x2, y2) = line[-2], line[-1]
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        (x1, y1), (x2, y2) = line[0], line[-1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    reach = 1000.0
    axis = LineString(
        [
            (center.x - ux * reach, center.y - uy * reach),
            (center.x + ux * reach, center.y + uy * reach),
        ]
    )
    crossing = axis.intersection(polygon.boundary)
    points = [(c[0], c[1]) for g in getattr(crossing, "geoms", [crossing]) for c in g.coords]
    if points:
        along = sorted(points, key=lambda p: (p[0] - center.x) * ux + (p[1] - center.y) * uy)
        front, back = along[0], along[-1]
    else:
        front = back = (center.x, center.y)
    return GreenPosition(
        front=proj.geo(*front),
        center=proj.geo(center.x, center.y),
        back=proj.geo(*back),
        outline=tuple(proj.geo(x, y) for x, y in _simplified_outline(polygon)),
        source=PositionSource.OSM,
    )


def match_hole_map(
    area: OsmArea,
    *,
    latitude: float,
    longitude: float,
    card: Sequence[CardHole],
    physical_holes: int,
) -> OsmHoleMapCandidate | None:
    """El mapa del campo en esa coordenada, o None si OSM no tiene su contorno cerca."""
    proj = _Projection(latitude, longitude)
    chosen = _choose_outline(_outlines(area, proj))
    if chosen is None:
        return None
    reference, outline = chosen
    inside = outline.buffer(HOLE_INSIDE_MARGIN_M)
    by_number = {hole.number: hole for hole in card}
    greens = [g for g in (_green_polygon([proj.xy(p) for p in w.points]) for w in area.greens) if g]

    discarded: Counter[DiscardReason] = Counter()
    candidates: dict[int, list[tuple[OsmWay, list[tuple[float, float]]]]] = {}
    for way in area.holes:
        line = [proj.xy(p) for p in way.points]
        if not inside.contains(LineString(line).interpolate(0.5, normalized=True)):
            continue
        number = _int_tag(way, "ref")
        if number is None or not MIN_HOLE_NUMBER <= number <= MAX_HOLE_NUMBER:
            discarded[DiscardReason.NO_NUMBER] += 1
            continue
        if number > physical_holes or number not in by_number:
            discarded[DiscardReason.BEYOND_COURSE] += 1
            continue
        par = _int_tag(way, "par")
        if par is not None and par != by_number[number].par:
            discarded[DiscardReason.PAR_MISMATCH] += 1
            continue
        candidates.setdefault(number, []).append((way, line))

    holes: list[MappedHole] = []
    for number, options in sorted(candidates.items()):
        chosen_ones = options
        if len(options) > 1:
            chosen_ones = [
                o for o in options if _int_tag(o[0], "handicap") == by_number[number].stroke_index
            ]
            if len(chosen_ones) != 1:
                discarded[DiscardReason.AMBIGUOUS] += 1
                continue
        _, line = chosen_ones[0]
        holes.append(_mapped_hole(number, line, greens, proj))

    return OsmHoleMapCandidate(
        osm_reference=reference, holes=tuple(holes), discarded=dict(discarded)
    )


def _mapped_hole(
    number: int, line: list[tuple[float, float]], greens: list[Polygon], proj: _Projection
) -> MappedHole:
    def distance_to_green(point: tuple[float, float]) -> float:
        return min((g.distance(Point(point)) for g in greens), default=math.inf)

    # OSM dibuja el hoyo de la salida al green. Solo se gira si su final no tiene
    # ningún green cerca y su principio sí: la salida suele estar pegada al green
    # del hoyo anterior, y comparar sin más los dos extremos giraría los buenos
    start, end_distance = distance_to_green(line[0]), distance_to_green(line[-1])
    if end_distance > MAX_GREEN_DISTANCE_M and start <= MAX_GREEN_DISTANCE_M:
        line = list(reversed(line))  # dibujada del green a la salida
    end = Point(line[-1])
    nearest = min(greens, key=lambda g: g.distance(end), default=None)
    green = None
    if nearest is not None and nearest.distance(end) <= MAX_GREEN_DISTANCE_M:
        green = _green_position(nearest, line, proj)
    return MappedHole(
        number=number,
        play_line=tuple(proj.geo(x, y) for x, y in line),
        line_source=PositionSource.OSM,
        green=green,
    )
