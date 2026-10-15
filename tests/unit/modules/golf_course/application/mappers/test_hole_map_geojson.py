"""
Tests del mapa de hoyos en GeoJSON (BE #532), el que pintará el front.

GeoJSON pone la longitud ANTES que la latitud, al revés que el resto de la app:
es el error más fácil y el que dejaría cada hoyo en mitad del océano.
"""

from datetime import datetime

from src.modules.golf_course.application.mappers.hole_map_geojson import (
    OSM_ATTRIBUTION,
    to_hole_map_dto,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource

IMPORTADO = datetime(2026, 10, 15, 9, 0, 0, 123456)
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.285, longitude=-5.331)
DELANTE = GeoPoint(latitude=36.2898, longitude=-5.3321)
CENTRO = GeoPoint(latitude=36.29, longitude=-5.332)
FONDO = GeoPoint(latitude=36.2902, longitude=-5.3319)
CONTORNO = (
    GeoPoint(latitude=36.2897, longitude=-5.3323),
    GeoPoint(latitude=36.2903, longitude=-5.3323),
    GeoPoint(latitude=36.2903, longitude=-5.3317),
)


def _map(*holes: MappedHole) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=GolfCourseId.generate(),
        holes=holes,
        osm_reference="way/1",
        imported_at=IMPORTADO,
    )


def _hole_with_green(number=1, line_source=PositionSource.OSM, green_source=PositionSource.OSM):
    return MappedHole(
        number=number,
        play_line=(SALIDA, CODO, CENTRO),
        line_source=line_source,
        green=GreenPosition(
            front=DELANTE, center=CENTRO, back=FONDO, outline=CONTORNO, source=green_source
        ),
    )


def _features(dto, kind):
    return [f for f in dto.geojson.features if f.properties["kind"] == kind]


def test_j1_play_line_is_a_linestring_in_lon_lat_order():
    """
    GIVEN: Un hoyo con su línea de juego (salida, codo, green)
    WHEN: Se pasa a GeoJSON
    THEN: Es un LineString con los puntos en orden y [longitud, latitud]
    """
    dto = to_hole_map_dto(_map(_hole_with_green()))

    (line,) = _features(dto, "play_line")
    assert line.geometry.type == "LineString"
    assert [tuple(c) for c in line.geometry.coordinates] == [
        (-5.33, 36.28),
        (-5.331, 36.285),
        (-5.332, 36.29),
    ]
    assert line.properties == {"hole": 1, "kind": "play_line", "source": "OSM"}


def test_j2_green_points_and_closed_outline():
    """
    GIVEN: Un hoyo con green y contorno
    WHEN: Se pasa a GeoJSON
    THEN: Delante, centro y fondo son puntos [lon, lat]; el contorno es un
         polígono con el anillo cerrado
    """
    dto = to_hole_map_dto(_map(_hole_with_green(green_source=PositionSource.PLAYER)))

    for kind, point in (("green_front", DELANTE), ("green_center", CENTRO), ("green_back", FONDO)):
        (feature,) = _features(dto, kind)
        assert feature.geometry.type == "Point"
        assert tuple(feature.geometry.coordinates) == (point.longitude, point.latitude)
        assert feature.properties == {"hole": 1, "kind": kind, "source": "PLAYER"}
    (outline,) = _features(dto, "green_outline")
    assert outline.geometry.type == "Polygon"
    ring = [tuple(c) for c in outline.geometry.coordinates[0]]
    assert ring[0] == ring[-1] == (-5.3323, 36.2897)
    assert len(ring) == 4


def test_j2_green_without_outline_has_no_polygon():
    """
    GIVEN: Un green marcado por un jugador, sin contorno
    WHEN: Se pasa a GeoJSON
    THEN: Tiene sus tres puntos pero ningún polígono
    """
    hole = MappedHole(
        number=2,
        play_line=(SALIDA, CENTRO),
        line_source=PositionSource.PLAYER,
        green=GreenPosition(front=DELANTE, center=CENTRO, back=FONDO, source=PositionSource.PLAYER),
    )

    dto = to_hole_map_dto(_map(hole))

    assert _features(dto, "green_outline") == []
    assert len(_features(dto, "green_center")) == 1


def test_j3_hole_without_green_is_only_its_line_and_is_pending():
    """
    GIVEN: Un hoyo 4 sin green y un hoyo 1 con green
    WHEN: Se pasa a GeoJSON
    THEN: Del 4 solo sale la línea, y aparece entre los pendientes de marcar green
    """
    pendiente = MappedHole(number=4, play_line=(SALIDA, CODO), line_source=PositionSource.OSM)

    dto = to_hole_map_dto(_map(_hole_with_green(), pendiente))

    kinds_4 = [f.properties["kind"] for f in dto.geojson.features if f.properties["hole"] == 4]
    assert kinds_4 == ["play_line"]
    assert dto.holes_needing_green == [4]


def test_j4_attribution_when_something_comes_from_osm():
    """
    GIVEN: Un mapa con alguna posición de OSM
    WHEN: Se pasa a GeoJSON
    THEN: Lleva la atribución que pide la licencia ODbL
    """
    dto = to_hole_map_dto(
        _map(_hole_with_green(line_source=PositionSource.MANUAL, green_source=PositionSource.OSM))
    )

    assert dto.attribution == OSM_ATTRIBUTION == "© OpenStreetMap contributors (ODbL)"


def test_j4_no_attribution_without_osm():
    """
    GIVEN: Un mapa sin ninguna posición de OSM
    WHEN: Se pasa a GeoJSON
    THEN: No lleva atribución
    """
    dto = to_hole_map_dto(
        _map(
            _hole_with_green(line_source=PositionSource.MANUAL, green_source=PositionSource.PLAYER)
        )
    )

    assert dto.attribution is None


def test_j5_metadata_outside_the_geojson():
    """
    GIVEN: Un mapa pendiente
    WHEN: Se pasa a GeoJSON
    THEN: Fuera van el campo, el estado y la versión (la fecha de importación exacta)
    """
    hole_map = _map(_hole_with_green())

    dto = to_hole_map_dto(hole_map)

    assert dto.golf_course_id == str(hole_map.golf_course_id)
    assert dto.status == "PENDING_REVIEW"
    assert dto.version == IMPORTADO
    assert dto.geojson.type == "FeatureCollection"
    assert dto.holes_needing_green == []
