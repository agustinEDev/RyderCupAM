"""
Tests de las posiciones del mapa de un hoyo (BE #532): punto, green y hoyo.

El mapa sirve para dar distancias en el campo, así que lo que se protege aquí es
que no entre un dato que las falsee: una coordenada imposible, un contorno que no
encierra nada o un hoyo sin salida desde la que medir.
"""

import math

import pytest

from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource

SALIDA = GeoPoint(latitude=36.28500, longitude=-5.32900)
CODO = GeoPoint(latitude=36.28650, longitude=-5.32850)
DELANTE = GeoPoint(latitude=36.28780, longitude=-5.32820)
CENTRO = GeoPoint(latitude=36.28790, longitude=-5.32815)
FONDO = GeoPoint(latitude=36.28800, longitude=-5.32810)
CONTORNO = (
    GeoPoint(latitude=36.28775, longitude=-5.32830),
    GeoPoint(latitude=36.28805, longitude=-5.32830),
    GeoPoint(latitude=36.28805, longitude=-5.32800),
    GeoPoint(latitude=36.28775, longitude=-5.32800),
)


def _green(outline: tuple[GeoPoint, ...] = CONTORNO) -> GreenPosition:
    return GreenPosition(
        front=DELANTE, center=CENTRO, back=FONDO, outline=outline, source=PositionSource.OSM
    )


# ============================================================================
# P — Punto
# ============================================================================


def test_p1_point_keeps_its_coordinates():
    """
    GIVEN: Una latitud y una longitud válidas
    WHEN: Se construye el punto
    THEN: Las conserva tal cual
    """
    point = GeoPoint(latitude=36.2858, longitude=-5.3247)

    assert point.latitude == 36.2858
    assert point.longitude == -5.3247


@pytest.mark.parametrize("latitude", [-90.0001, 90.0001])
def test_p2_point_rejects_latitude_out_of_range(latitude):
    """
    GIVEN: Una latitud fuera de -90..90
    WHEN: Se construye el punto
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="latitude"):
        GeoPoint(latitude=latitude, longitude=0.0)


@pytest.mark.parametrize("longitude", [-180.0001, 180.0001])
def test_p3_point_rejects_longitude_out_of_range(longitude):
    """
    GIVEN: Una longitud fuera de -180..180
    WHEN: Se construye el punto
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="longitude"):
        GeoPoint(latitude=0.0, longitude=longitude)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(math.nan, 0.0), (0.0, math.nan), (math.inf, 0.0), (0.0, -math.inf)],
)
def test_p4_point_rejects_nan_and_infinity(latitude, longitude):
    """
    GIVEN: Un NaN o un infinito en cualquiera de las dos coordenadas
    WHEN: Se construye el punto
    THEN: Se rechaza (un NaN pasaría las comparaciones de rango sin saltar)
    """
    with pytest.raises(ValueError, match="finite"):
        GeoPoint(latitude=latitude, longitude=longitude)


@pytest.mark.parametrize(("latitude", "longitude"), [(True, 0.0), (0.0, False)])
def test_p5_point_rejects_booleans(latitude, longitude):
    """
    GIVEN: Un booleano como coordenada (en Python, True vale 1)
    WHEN: Se construye el punto
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="number"):
        GeoPoint(latitude=latitude, longitude=longitude)


def test_p1b_point_limits_are_valid():
    """
    GIVEN: Los extremos exactos de los rangos
    WHEN: Se construye el punto
    THEN: Son válidos
    """
    GeoPoint(latitude=-90.0, longitude=-180.0)
    GeoPoint(latitude=90.0, longitude=180.0)


# ============================================================================
# G — Green
# ============================================================================


def test_g1_green_with_three_points_and_outline():
    """
    GIVEN: Delante, centro, fondo y contorno
    WHEN: Se construye el green
    THEN: Los conserva, con su origen
    """
    green = _green()

    assert (green.front, green.center, green.back) == (DELANTE, CENTRO, FONDO)
    assert green.outline == CONTORNO
    assert green.source is PositionSource.OSM


def test_g2_green_outline_is_optional():
    """
    GIVEN: Un green con delante, centro y fondo pero sin contorno (lo marcó un jugador)
    WHEN: Se construye
    THEN: Es válido y su contorno está vacío
    """
    green = GreenPosition(front=DELANTE, center=CENTRO, back=FONDO, source=PositionSource.PLAYER)

    assert green.outline == ()


@pytest.mark.parametrize("points", [1, 2])
def test_g3_green_outline_needs_three_points(points):
    """
    GIVEN: Un contorno de menos de tres puntos
    WHEN: Se construye el green
    THEN: Se rechaza: no encierra ninguna superficie
    """
    with pytest.raises(ValueError, match="outline"):
        _green(outline=CONTORNO[:points])


def test_g3b_green_outline_is_stored_as_tuple():
    """
    GIVEN: Un contorno pasado como lista
    WHEN: Se construye el green
    THEN: Se guarda como tupla, para que el valor siga siendo inmutable
    """
    green = GreenPosition(
        front=DELANTE, center=CENTRO, back=FONDO, outline=list(CONTORNO), source=PositionSource.OSM
    )

    assert green.outline == CONTORNO


# ============================================================================
# H — Hoyo mapeado
# ============================================================================


@pytest.mark.parametrize("number", [1, 18])
def test_h1_hole_number_from_1_to_18(number):
    """
    GIVEN: Un número de hoyo entre 1 y 18
    WHEN: Se construye el hoyo
    THEN: Es válido
    """
    hole = MappedHole(
        number=number, play_line=(SALIDA, CENTRO), line_source=PositionSource.OSM, green=_green()
    )

    assert hole.number == number


@pytest.mark.parametrize("number", [0, 19])
def test_h2_hole_number_out_of_range(number):
    """
    GIVEN: Un 0 o un 19
    WHEN: Se construye el hoyo
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="number"):
        MappedHole(
            number=number, play_line=(SALIDA, CENTRO), line_source=PositionSource.OSM, green=None
        )


@pytest.mark.parametrize("number", [1.5, 3.0, True])
def test_h2b_hole_number_must_be_an_integer(number):
    """
    GIVEN: Un número de hoyo que no es un entero (1.5, 3.0 o True)
    WHEN: Se construye el hoyo
    THEN: Se rechaza: acabaría tal cual en el JSONB
    """
    with pytest.raises(ValueError, match="integer"):
        MappedHole(
            number=number, play_line=(SALIDA, CENTRO), line_source=PositionSource.OSM, green=None
        )


def test_h3_hole_without_green_is_pending_to_mark():
    """
    GIVEN: Un hoyo con su salida pero sin green
    WHEN: Se construye
    THEN: Es válido y queda con el green pendiente de marcar
    """
    hole = MappedHole(number=7, play_line=(SALIDA, CODO), line_source=PositionSource.OSM)

    assert hole.green is None
    assert hole.needs_green is True


def test_h3_hole_with_green_does_not_need_one():
    """
    GIVEN: Un hoyo con salida y green
    WHEN: Se pregunta si le falta el green
    THEN: No le falta
    """
    hole = MappedHole(
        number=7, play_line=(SALIDA, CENTRO), line_source=PositionSource.OSM, green=_green()
    )

    assert hole.needs_green is False


def test_h3b_hole_without_tee_is_rejected():
    """
    GIVEN: Un hoyo sin ningún punto en su línea (sin salida)
    WHEN: Se construye
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="play line"):
        MappedHole(number=1, play_line=(), line_source=PositionSource.OSM)


def test_h4_each_position_keeps_its_source():
    """
    GIVEN: Una línea de OSM y un green que marcó un jugador
    WHEN: Se construye el hoyo
    THEN: Cada posición conserva su propio origen (licencia ODbL)
    """
    green = GreenPosition(front=DELANTE, center=CENTRO, back=FONDO, source=PositionSource.PLAYER)
    hole = MappedHole(
        number=3, play_line=(SALIDA, CENTRO), line_source=PositionSource.OSM, green=green
    )

    assert hole.line_source is PositionSource.OSM
    assert hole.green is not None
    assert hole.green.source is PositionSource.PLAYER


def test_h4_sources_are_osm_manual_and_player():
    """
    GIVEN: Los orígenes posibles
    WHEN: Se enumeran
    THEN: Son OSM, MANUAL y PLAYER
    """
    assert {source.value for source in PositionSource} == {"OSM", "MANUAL", "PLAYER"}


def test_h5_hole_keeps_its_play_line_and_tee_is_first_point():
    """
    GIVEN: Una línea de juego con un codo (dogleg)
    WHEN: Se construye el hoyo
    THEN: Conserva todos los puntos en orden y su salida es el primero
    """
    hole = MappedHole(
        number=5, play_line=[SALIDA, CODO, CENTRO], line_source=PositionSource.OSM, green=_green()
    )

    assert hole.play_line == (SALIDA, CODO, CENTRO)
    assert hole.tee == SALIDA


def test_h5b_play_line_needs_two_points():
    """
    GIVEN: Una línea de un solo punto
    WHEN: Se construye el hoyo
    THEN: Se rechaza: una línea de juego va de la salida a algún sitio
    """
    with pytest.raises(ValueError, match="play line"):
        MappedHole(number=1, play_line=(SALIDA,), line_source=PositionSource.OSM)
