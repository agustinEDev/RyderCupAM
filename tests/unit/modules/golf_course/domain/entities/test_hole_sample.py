"""
Tests de la muestra anónima de un hoyo (BE #532, reglas del 16 oct 2026).

Una muestra es la salida, hasta dos codos y el centro del green que manda un
jugador al jugar un hoyo. No guarda quién la mandó, y de cuándo llegó solo el
día (UTC): la hora ayudaría a saber quién estaba en el campo. El id lo pone el
móvil (para que un reenvío cuente una vez) y no dice nada de quién la manda.
Los límites frenan muestras absurdas (un toque en el hoyo de al lado, o a mitad
de camino).

| Caso                                         | Resultado                               |
|----------------------------------------------|-----------------------------------------|
| Salida, dos codos y green a 300 m            | Se crea, con el id del móvil y el día UTC |
| Solo el día, sin hora                        | `received_on` es un `date`               |
| Id que no es un UUID                         | InvalidHoleSampleError                   |
| La barra: color y género (o sin género)      | Se guardan tal cual                      |
| Color o género que no son sus enums          | InvalidHoleSampleError                   |
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
| Un datetime como día                         | InvalidHoleSampleError                   |
| Los errores                                  | Todos son InvalidHoleSampleError         |
"""

from datetime import UTC, date, datetime
from uuid import uuid4

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
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender

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
        "id": uuid4(),
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 1,
        "tee_color": TeeColor.YELLOW,
        "tee_gender": Gender.MALE,
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
    THEN: Lleva sus puntos en orden, el id que puso el móvil y el día de hoy en UTC
    """
    sample_id = uuid4()
    antes = datetime.now(UTC).date()

    sample = _create(id=sample_id, hole_number=7, bends=[CODO, CODO_2])

    assert sample.hole_number == 7
    assert sample.tee == SALIDA
    assert sample.bends == (CODO, CODO_2)
    assert sample.green_center == GREEN
    assert sample.id == sample_id
    assert antes <= sample.received_on <= datetime.now(UTC).date()


def test_d1_only_the_day_is_kept():
    """
    GIVEN: Una muestra recién creada
    WHEN: Se mira cuándo llegó
    THEN: Es un día, sin hora (un datetime también es un date en Python: se descarta)
    """
    received_on = _create().received_on

    assert isinstance(received_on, date)
    assert not isinstance(received_on, datetime)
    assert not hasattr(_create(), "created_at")


@pytest.mark.parametrize("gender", [Gender.MALE, Gender.FEMALE, None])
def test_d1_the_tee_is_kept(gender):
    """
    GIVEN: Una muestra desde las rojas de hombre, de mujer o sin género
    WHEN: Se crea
    THEN: Lleva su color y su género (None = barra sin género)
    """
    sample = _create(tee_color=TeeColor.RED, tee_gender=gender)

    assert (sample.tee_color, sample.tee_gender) == (TeeColor.RED, gender)


@pytest.mark.parametrize(
    "changes",
    [{"tee_color": "YELLOW"}, {"tee_color": None}, {"tee_gender": "MALE"}, {"tee_gender": 1}],
)
def test_d1_the_tee_must_use_its_enums(changes):
    """
    GIVEN: Un color en texto o nulo, o un género en texto o un número
    WHEN: Se crea la muestra
    THEN: InvalidHoleSampleError (la entrada los convierte; el dominio no adivina)
    """
    with pytest.raises(InvalidHoleSampleError):
        _create(**changes)


@pytest.mark.parametrize("bad_id", ["9f1c0e7e-0000-4000-8000-000000000000", None, 7])
def test_d1_the_id_must_be_a_uuid(bad_id):
    """
    GIVEN: Un id en texto, nulo o un número
    WHEN: Se crea la muestra
    THEN: InvalidHoleSampleError (lo convierte a UUID la entrada, no el dominio)
    """
    with pytest.raises(InvalidHoleSampleError):
        _create(id=bad_id)


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
    THEN: Se carga tal cual, con su id y su día
    """
    sample_id = uuid4()
    at = date(2026, 10, 16)

    sample = HoleSample.reconstruct(
        id=sample_id,
        golf_course_id=GolfCourseId.generate(),
        hole_number=4,
        tee_color=TeeColor.RED,
        tee_gender=None,
        tee=SALIDA,
        bends=[CODO],
        green_center=_north(10),
        received_on=at,
    )

    assert (sample.id, sample.received_on, sample.bends) == (sample_id, at, (CODO,))


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
            tee_color=TeeColor.RED,
            tee_gender=None,
            tee=SALIDA,
            bends=[CODO, CODO, CODO],
            green_center=GREEN,
            received_on=date(2026, 10, 16),
        )


def test_d5_every_rejection_is_an_invalid_sample():
    """
    GIVEN: Los errores de distancia
    WHEN: Se mira su clase
    THEN: Los dos son InvalidHoleSampleError (el caso de uso los descarta todos igual)
    """
    assert issubclass(HoleSampleOutOfRangeError, InvalidHoleSampleError)
    assert issubclass(HoleSampleFarFromCourseError, InvalidHoleSampleError)


def test_d5_a_time_cannot_sneak_in_as_the_day():
    """
    GIVEN: Una fecha con hora (un datetime también es un date en Python)
    WHEN: Se reconstruye una muestra con ella
    THEN: InvalidHoleSampleError: de la llegada solo se guarda el día
    """
    with pytest.raises(InvalidHoleSampleError):
        HoleSample.reconstruct(
            id=uuid4(),
            golf_course_id=GolfCourseId.generate(),
            hole_number=4,
            tee_color=TeeColor.RED,
            tee_gender=None,
            tee=SALIDA,
            bends=[],
            green_center=GREEN,
            received_on=datetime(2026, 10, 16, 9, 30),
        )
