"""
Tests de la muestra anónima de un hoyo (BE #532, reglas del 16 oct 2026).

Una muestra es la salida, hasta dos codos y el centro del green que manda un
jugador al jugar un hoyo. No guarda quién la mandó. Los límites frenan muestras
absurdas (un toque en el hoyo de al lado, o a mitad de camino).

| Caso                                         | Resultado                               |
|----------------------------------------------|-----------------------------------------|
| Salida, dos codos y green a 300 m            | Se crea, con id propio y fecha UTC naive |
| Sin codos                                    | Se crea                                  |
| Tres codos                                   | InvalidHoleSampleError                   |
| Hoyo 0 o 19, o un número que no es entero    | InvalidHoleSampleError                   |
| Salida, codo o green que no son GeoPoint     | InvalidHoleSampleError                   |
| Green a 30 m o a 800 m de la salida          | HoleSampleOutOfRangeError                |
| Green justo a 40 m y a 750 m                 | Se crea (los bordes valen)               |
| Un punto (salida, codo o green) a más de 3 km | HoleSampleFarFromCourseError            |
| Todo a menos de 3 km del campo               | Se crea                                  |
| Campo sin ubicación                          | No se mira la distancia al campo         |
| Leída de la BD (`reconstruct`)               | No se vuelven a medir distancias         |
| Los errores                                  | Todos son InvalidHoleSampleError         |
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.modules.golf_course.domain.entities.hole_sample import (
    MAX_BENDS,
    MAX_SAMPLES_PER_HOLE,
    HoleSample,
    HoleSampleFarFromCourseError,
    HoleSampleOutOfRangeError,
    InvalidHoleSampleError,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
CODO_2 = GeoPoint(latitude=36.282, longitude=-5.3312)
CAMPO = GeoPoint(latitude=36.285, longitude=-5.33)


def _north(metres: float, of: GeoPoint = SALIDA) -> GeoPoint:
    return GeoPoint(latitude=of.latitude + metres / M_PER_DEGREE, longitude=of.longitude)


GREEN = _north(300)


def _create(**changes) -> HoleSample:
    args = {
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 1,
        "tee": SALIDA,
        "bends": (),
        "green_center": GREEN,
        "course_location": None,
    }
    args.update(changes)
    return HoleSample.create(**args)


# ============================================================================
# D1 — Una muestra buena
# ============================================================================


def test_d1_sample_with_two_bends_is_created():
    """
    GIVEN: Salida, dos codos y green a 300 m, en el hoyo 7
    WHEN: Se crea la muestra
    THEN: Lleva sus puntos en orden, un id nuevo y la fecha de ahora en UTC sin zona
    """
    antes = datetime.now(UTC).replace(tzinfo=None)

    sample = _create(hole_number=7, bends=[CODO, CODO_2])

    assert sample.hole_number == 7
    assert sample.tee == SALIDA
    assert sample.bends == (CODO, CODO_2)
    assert sample.green_center == GREEN
    assert isinstance(sample.id, UUID)
    assert sample.created_at.tzinfo is None
    assert antes <= sample.created_at <= datetime.now(UTC).replace(tzinfo=None)


def test_d1_each_sample_has_its_own_id():
    """
    GIVEN: Dos muestras iguales del mismo hoyo
    WHEN: Se crean
    THEN: Tienen ids distintos (cada envío cuenta, aunque sea de la misma persona)
    """
    assert _create().id != _create().id


def test_d1_sample_without_bends_is_created():
    """
    GIVEN: Una salida y un green, sin codos
    WHEN: Se crea la muestra
    THEN: No lleva codos
    """
    assert _create().bends == ()


def test_d1_the_cap_is_three():
    """
    GIVEN: La regla del 16 oct
    WHEN: Se mira cuántas muestras se guardan por hoyo y cuántos codos caben
    THEN: Tres muestras y dos codos
    """
    assert (MAX_SAMPLES_PER_HOLE, MAX_BENDS) == (3, 2)


def test_d1_the_sample_does_not_know_who_sent_it():
    """
    GIVEN: Una muestra
    WHEN: Se busca algo de quién la mandó
    THEN: No hay nada: la entidad ni lo recibe ni lo guarda
    """
    sample = _create()

    assert not any("user" in name for name in dir(sample))


# ============================================================================
# D2 — Muestras mal formadas
# ============================================================================


def test_d2_three_bends_are_rejected():
    """
    GIVEN: Tres codos
    WHEN: Se crea la muestra
    THEN: InvalidHoleSampleError
    """
    with pytest.raises(InvalidHoleSampleError):
        _create(bends=[CODO, CODO_2, CODO])


@pytest.mark.parametrize("hole", [0, 19, -1, 3.0, True, "1"])
def test_d2_hole_outside_a_round_is_rejected(hole):
    """
    GIVEN: El hoyo 0, el 19, uno negativo, o algo que no es un entero
    WHEN: Se crea la muestra
    THEN: InvalidHoleSampleError
    """
    with pytest.raises(InvalidHoleSampleError):
        _create(hole_number=hole)


@pytest.mark.parametrize("hole", [1, 10, 18])
def test_d2_any_hole_of_a_round_is_fine(hole):
    """
    GIVEN: El hoyo 1, el 10 o el 18
    WHEN: Se crea la muestra
    THEN: Se crea
    """
    assert _create(hole_number=hole).hole_number == hole


@pytest.mark.parametrize(
    "changes",
    [
        {"tee": (36.28, -5.33)},
        {"tee": None},
        {"green_center": None},
        {"bends": [(36.28, -5.33)]},
        {"golf_course_id": "no-es-un-id"},
    ],
)
def test_d2_points_must_be_geopoints(changes):
    """
    GIVEN: Una salida, un green o un codo que no son GeoPoint, o un campo sin id
    WHEN: Se crea la muestra
    THEN: InvalidHoleSampleError
    """
    with pytest.raises(InvalidHoleSampleError):
        _create(**changes)


# ============================================================================
# D3 — De la salida al green, 40-750 m en recta
# ============================================================================


@pytest.mark.parametrize("metres", [30, 39.5, 750.5, 800])
def test_d3_green_too_close_or_too_far_from_the_tee(metres):
    """
    GIVEN: El green a 30 m, 39,5 m, 750,5 m u 800 m de la salida
    WHEN: Se crea la muestra
    THEN: HoleSampleOutOfRangeError
    """
    with pytest.raises(HoleSampleOutOfRangeError):
        _create(green_center=_north(metres))


@pytest.mark.parametrize("metres", [40.01, 749.99])
def test_d3_the_limits_are_inclusive(metres):
    """
    GIVEN: El green a 40 m y a 750 m de la salida (con un pelo de margen por la haversine)
    WHEN: Se crea la muestra
    THEN: Se crea
    """
    assert _create(green_center=_north(metres)).green_center == _north(metres)


def test_d3_a_long_dogleg_is_measured_in_a_straight_line():
    """
    GIVEN: Un green a 700 m en recta con un codo muy abierto (la línea pasa de 750 m)
    WHEN: Se crea la muestra
    THEN: Se crea: la regla mide la recta de la salida al green, no la línea
    """
    codo_abierto = GeoPoint(latitude=SALIDA.latitude + 350 / M_PER_DEGREE, longitude=-5.326)

    sample = _create(bends=[codo_abierto], green_center=_north(700))

    assert sample.bends == (codo_abierto,)


# ============================================================================
# D4 — Nada a más de 3 km del campo
# ============================================================================


@pytest.mark.parametrize("which", ["tee", "bend", "green_center"])
def test_d4_any_point_far_from_the_course_is_rejected(which):
    """
    GIVEN: Un campo con ubicación, y la salida, un codo o el green a más de 3 km
    WHEN: Se crea la muestra
    THEN: HoleSampleFarFromCourseError
    """
    lejos = _north(3100, of=CAMPO)
    changes = {
        "tee": {"tee": lejos, "green_center": _north(300, of=lejos)},
        "bend": {"bends": [lejos], "green_center": GREEN},
        "green_center": {
            "tee": _north(-400, of=lejos),
            "green_center": lejos,
        },
    }[which]
    # El de la salida lleva su green cerca de ella: tampoco a 3 km. El del green,
    # su salida a 2,7 km del campo (dentro), para que salte solo el green
    with pytest.raises(HoleSampleFarFromCourseError):
        _create(course_location=CAMPO, **changes)


def test_d4_points_within_three_km_are_fine():
    """
    GIVEN: Un campo con ubicación a menos de 1 km de la salida, el codo y el green
    WHEN: Se crea la muestra
    THEN: Se crea
    """
    assert _create(course_location=CAMPO, bends=[CODO]).bends == (CODO,)


def test_d4_without_course_location_the_distance_is_not_checked():
    """
    GIVEN: Un campo sin ubicación y una muestra a cientos de km de cualquier sitio conocido
    WHEN: Se crea la muestra
    THEN: Se crea: sin ubicación no hay con qué comparar
    """
    lejos = GeoPoint(latitude=43.0, longitude=-8.0)

    sample = _create(tee=lejos, green_center=_north(300, of=lejos), course_location=None)

    assert sample.tee == lejos


# ============================================================================
# D5 — Leída de la base de datos, y la jerarquía de errores
# ============================================================================


def test_d5_reconstruct_does_not_measure_again():
    """
    GIVEN: Una muestra guardada con un green a 10 m (si mañana cambian los límites)
    WHEN: Se reconstruye desde la BD
    THEN: Se carga tal cual, con su id y su fecha
    """
    sample_id = uuid4()
    at = datetime(2026, 10, 16, 9, 0)

    sample = HoleSample.reconstruct(
        id=sample_id,
        golf_course_id=GolfCourseId.generate(),
        hole_number=4,
        tee=SALIDA,
        bends=[CODO],
        green_center=_north(10),
        created_at=at,
    )

    assert (sample.id, sample.created_at, sample.bends) == (sample_id, at, (CODO,))


def test_d5_reconstruct_still_rejects_three_bends():
    """
    GIVEN: Una fila con tres codos (la BD no lo permite, pero el dominio tampoco)
    WHEN: Se reconstruye
    THEN: InvalidHoleSampleError
    """
    with pytest.raises(InvalidHoleSampleError):
        HoleSample.reconstruct(
            id=uuid4(),
            golf_course_id=GolfCourseId.generate(),
            hole_number=4,
            tee=SALIDA,
            bends=[CODO, CODO, CODO],
            green_center=GREEN,
            created_at=datetime(2026, 10, 16, 9, 0),
        )


def test_d5_every_rejection_is_an_invalid_sample():
    """
    GIVEN: Los errores de distancia
    WHEN: Se mira su clase
    THEN: Los dos son InvalidHoleSampleError (el caso de uso los descarta todos igual)
    """
    assert issubclass(HoleSampleOutOfRangeError, InvalidHoleSampleError)
    assert issubclass(HoleSampleFarFromCourseError, InvalidHoleSampleError)
