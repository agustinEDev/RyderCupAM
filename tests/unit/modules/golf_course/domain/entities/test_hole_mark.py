"""
Tests de la marca de un hoyo hecha por un jugador (BE #532, PR C).

En un hoyo sin datos el jugador toca la salida y el centro del green (y, si es
un dogleg, arrastra hasta dos codos). Si el hoyo ya tiene salida, solo marca el
green. La marca es suya: la ve él al momento y los demás cuando la apruebe un
admin. Los límites frenan marcas absurdas: de la salida al green entre 40 y
750 m, y nada a más de 3 km del campo.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.entities.hole_mark import (
    MAX_BENDS,
    MAX_DISTANCE_FROM_COURSE_M,
    MAX_TEE_TO_GREEN_M,
    MIN_TEE_TO_GREEN_M,
    HoleMark,
    HoleMarkFarFromCourseError,
    HoleMarkOutOfRangeError,
    InvalidHoleMarkError,
    ensure_near_course,
    ensure_tee_to_green,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId

# Metros por grado de latitud con el radio de la Tierra que usamos (6 371 000 m)
M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180

SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)


def _north(metres: float, of: GeoPoint = SALIDA) -> GeoPoint:
    """El punto a tantos metros al norte de otro (misma longitud)."""
    return GeoPoint(latitude=of.latitude + metres / M_PER_DEGREE, longitude=of.longitude)


GREEN = _north(300)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
CODO_2 = GeoPoint(latitude=36.2820, longitude=-5.3312)


def _mark(**changes) -> HoleMark:
    data = {
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 1,
        "user_id": UserId.generate(),
        "tee": SALIDA,
        "bends": (),
        "green_center": GREEN,
    }
    data.update(changes)
    return HoleMark.create(**data)


# ============================================================================
# D1 — Lo que guarda
# ============================================================================


def test_d1_full_mark_keeps_its_points_and_dates():
    """
    GIVEN: Una salida, un codo y el centro del green
    WHEN: Se crea la marca
    THEN: Guarda campo, hoyo, jugador y los puntos; creada y actualizada a la vez
    """
    course, user = GolfCourseId.generate(), UserId.generate()

    mark = _mark(golf_course_id=course, user_id=user, hole_number=7, bends=[CODO])

    assert mark.golf_course_id == course
    assert mark.user_id == user
    assert mark.hole_number == 7
    assert mark.tee == SALIDA
    assert mark.bends == (CODO,)
    assert mark.green_center == GREEN
    assert isinstance(mark.created_at, datetime)
    assert mark.created_at.tzinfo is None
    assert mark.updated_at == mark.created_at


def test_d1_play_line_goes_tee_bends_green():
    """
    GIVEN: Una marca con dos codos
    WHEN: Se pide su línea de juego
    THEN: Salida, codos en orden y centro del green
    """
    mark = _mark(bends=(CODO, CODO_2))

    assert mark.play_line == (SALIDA, CODO, CODO_2, GREEN)


def test_d1_green_only_mark_has_no_tee_and_its_line_is_empty():
    """
    GIVEN: Un hoyo que ya tiene salida, y el jugador solo marca el green
    WHEN: Se crea la marca sin salida
    THEN: Vale; no tiene salida, ni codos, ni línea propia
    """
    mark = _mark(tee=None)

    assert mark.tee is None
    assert mark.bends == ()
    assert mark.play_line == ()


# ============================================================================
# D2 — Codos
# ============================================================================


def test_d2_up_to_two_bends():
    """
    GIVEN: Dos codos (doble dogleg)
    WHEN: Se crea la marca
    THEN: Vale; con tres, no
    """
    assert MAX_BENDS == 2
    assert len(_mark(bends=[CODO, CODO_2]).bends) == 2

    with pytest.raises(InvalidHoleMarkError):
        _mark(bends=[CODO, CODO_2, CODO])


def test_d2_bends_need_a_tee():
    """
    GIVEN: Una marca solo de green (sin salida)
    WHEN: Lleva un codo
    THEN: Error: sin salida propia no hay línea que doblar
    """
    with pytest.raises(InvalidHoleMarkError):
        _mark(tee=None, bends=[CODO])


def test_d2_bends_must_be_points():
    """
    GIVEN: Un codo que no es un GeoPoint
    WHEN: Se crea la marca
    THEN: Error de dato, no un fallo al guardar
    """
    with pytest.raises(InvalidHoleMarkError):
        _mark(bends=[(36.28, -5.33)])


# ============================================================================
# D3 — Número de hoyo y tipos
# ============================================================================


@pytest.mark.parametrize("number", [1, 18])
def test_d3_hole_numbers_from_1_to_18(number):
    """
    GIVEN: El hoyo 1 o el 18
    WHEN: Se crea la marca
    THEN: Vale
    """
    assert _mark(hole_number=number).hole_number == number


@pytest.mark.parametrize("number", [0, 19, -1, True, 3.0, "3", None])
def test_d3_other_hole_numbers_are_invalid(number):
    """
    GIVEN: Un número fuera de 1-18, o que no es un entero (True es 1 en Python)
    WHEN: Se crea la marca
    THEN: Error
    """
    with pytest.raises(InvalidHoleMarkError):
        _mark(hole_number=number)


@pytest.mark.parametrize(
    "changes",
    [
        {"green_center": None},
        {"green_center": (36.29, -5.33)},
        {"tee": (36.28, -5.33)},
        {"golf_course_id": "x"},
        {"user_id": "x"},
    ],
)
def test_d3_wrong_types_are_invalid(changes):
    """
    GIVEN: Un green, una salida, un campo o un jugador del tipo equivocado
    WHEN: Se crea la marca
    THEN: Error de dato
    """
    with pytest.raises(InvalidHoleMarkError):
        _mark(**changes)


# ============================================================================
# D4 — De la salida al green: entre 40 y 750 m
# ============================================================================


@pytest.mark.parametrize(
    "metres", [MIN_TEE_TO_GREEN_M + 0.001, 41, 749, MAX_TEE_TO_GREEN_M - 0.001]
)
def test_d4_tee_to_green_within_limits(metres):
    """
    GIVEN: El green a 40, 41, 749 o 750 m de la salida (con un milímetro de holgura por los decimales)
    WHEN: Se crea la marca
    THEN: Vale (los límites cuentan)
    """
    assert (MIN_TEE_TO_GREEN_M, MAX_TEE_TO_GREEN_M) == (40, 750)
    assert _mark(green_center=_north(metres)).green_center == _north(metres)


@pytest.mark.parametrize("metres", [0, 39.5, 750.5, 2000])
def test_d4_tee_to_green_out_of_limits(metres):
    """
    GIVEN: El green a menos de 40 m o a más de 750 m de la salida
    WHEN: Se crea la marca
    THEN: HoleMarkOutOfRangeError
    """
    with pytest.raises(HoleMarkOutOfRangeError):
        _mark(green_center=_north(metres))


def test_d4_the_limit_is_straight_not_along_the_bends():
    """
    GIVEN: Green a 700 m en recta, con un codo muy abierto (la línea pasa de 750)
    WHEN: Se crea la marca
    THEN: Vale: el límite es de la salida al green en recta
    """
    lejos = GeoPoint(latitude=SALIDA.latitude + 350 / M_PER_DEGREE, longitude=-5.326)

    mark = _mark(green_center=_north(700), bends=[lejos])

    assert mark.bends == (lejos,)


@pytest.mark.parametrize("metres", [39.5, 750.5])
def test_d4_ensure_tee_to_green_for_a_green_only_mark(metres):
    """
    GIVEN: La salida que ya tiene el hoyo y un green marcado fuera de límites
    WHEN: Se comprueba (marca solo de green)
    THEN: HoleMarkOutOfRangeError; dentro de límites no dice nada
    """
    with pytest.raises(HoleMarkOutOfRangeError):
        ensure_tee_to_green(SALIDA, _north(metres))

    assert ensure_tee_to_green(SALIDA, _north(300)) is None


# ============================================================================
# D5 — Cerca del campo: 3 km como mucho
# ============================================================================


def test_d5_points_near_the_course_are_fine():
    """
    GIVEN: Una marca con todos sus puntos a menos de 3 km del campo
    WHEN: Se comprueba contra la ubicación del campo
    THEN: No dice nada (casi 3000 m también valen)
    """
    assert MAX_DISTANCE_FROM_COURSE_M == 3000
    campo = _north(-2699.99)  # el green queda a 2999,99 m del campo

    assert ensure_near_course(_mark(), campo) is None


@pytest.mark.parametrize("lejano", ["tee", "bend", "green_center"])
def test_d5_any_point_far_from_the_course_fails(lejano):
    """
    GIVEN: Una marca con la salida, un codo o el green a más de 3 km del campo
    WHEN: Se comprueba
    THEN: HoleMarkFarFromCourseError
    """
    if lejano == "tee":
        campo = GeoPoint(latitude=36.0, longitude=-5.33)
        mark = _mark(tee=_north(3100, of=campo), green_center=_north(2800, of=campo))
    elif lejano == "bend":
        # El codo, ~2,7 km al este de la salida; el campo, 450 m al oeste de ella
        mark = _mark(bends=[GeoPoint(latitude=36.28, longitude=-5.30)])
        campo = GeoPoint(latitude=36.28, longitude=-5.335)
    else:
        mark = _mark()
        campo = _north(-2702)

    with pytest.raises(HoleMarkFarFromCourseError):
        ensure_near_course(mark, campo)


def test_d5_green_only_mark_checks_its_green():
    """
    GIVEN: Una marca solo de green, con el green a más de 3 km del campo
    WHEN: Se comprueba
    THEN: HoleMarkFarFromCourseError
    """
    with pytest.raises(HoleMarkFarFromCourseError):
        ensure_near_course(_mark(tee=None), _north(-2702))


def test_d5_course_without_location_is_not_checked():
    """
    GIVEN: Un campo sin ubicación
    WHEN: Se comprueba la marca
    THEN: No dice nada: no hay con qué comparar
    """
    assert ensure_near_course(_mark(), None) is None


# ============================================================================
# D6 — Distancia entre dos puntos
# ============================================================================


def test_d6_distance_between_points():
    """
    GIVEN: Dos puntos a 300 m en el mismo meridiano
    WHEN: Se mide la distancia
    THEN: 300 m, igual en los dos sentidos; de un punto a sí mismo, 0
    """
    assert SALIDA.distance_to(GREEN) == pytest.approx(300, abs=0.01)
    assert GREEN.distance_to(SALIDA) == pytest.approx(300, abs=0.01)
    assert SALIDA.distance_to(SALIDA) == 0


def test_d6_distance_along_a_parallel_shrinks_with_latitude():
    """
    GIVEN: Dos puntos a 0,01° de longitud en la latitud 36,28
    WHEN: Se mide
    THEN: ~896 m (el coseno de la latitud), no los ~1112 del ecuador
    """
    este = GeoPoint(latitude=36.28, longitude=-5.32)

    assert SALIDA.distance_to(este) == pytest.approx(896.3, abs=0.5)
