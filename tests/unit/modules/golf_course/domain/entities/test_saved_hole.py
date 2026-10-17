"""
La línea que el admin guarda de un hoyo (BE #575, 17 oct 2026): una referencia
por hoyo, de la salida al green con sus codos, que ven todos los jugadores.

| Caso | Qué                                          | Resultado                          |
|------|----------------------------------------------|------------------------------------|
| G1   | salida, hasta 2 codos y green, a 40-750 m     | Se guarda con quién y cuándo       |
| G2   | tres codos, green a 30 m o a 800 m           | InvalidSavedHoleError              |
| G2   | hoyo 0 o 19, puntos que no son GeoPoint      | InvalidSavedHoleError              |
| G3   | un punto a más de 3 km del campo             | InvalidSavedHoleError              |
| G4   | reconstruir de la BD                         | Sin volver a medir                 |
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.entities.saved_hole import InvalidSavedHoleError, SavedHole
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CAMPO = GeoPoint(latitude=36.285, longitude=-5.33)


def _north(metres: float, of: GeoPoint = SALIDA) -> GeoPoint:
    return GeoPoint(latitude=of.latitude + metres / M_PER_DEGREE, longitude=of.longitude)


def _save(**changes) -> SavedHole:
    args = {
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 1,
        "tee": SALIDA,
        "bends": (_north(150),),
        "green_center": _north(300),
        "saved_by": UserId.generate(),
        "course_location": None,
    }
    args.update(changes)
    return SavedHole.create(**args)


def test_g1_a_line_with_its_bends_is_saved_with_who_and_when():
    admin = UserId.generate()

    hole = _save(saved_by=admin)

    assert hole.play_line == (SALIDA, _north(150), _north(300))
    assert hole.saved_by == admin
    assert isinstance(hole.saved_at, datetime)


def test_g1_without_bends():
    assert _save(bends=()).bends == ()


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"bends": (_north(50), _north(100), _north(150))}, id="tres codos"),
        pytest.param({"green_center": _north(30)}, id="green a 30 m"),
        pytest.param({"green_center": _north(800), "bends": ()}, id="green a 800 m"),
        pytest.param({"hole_number": 0}, id="hoyo 0"),
        pytest.param({"hole_number": 19}, id="hoyo 19"),
        pytest.param({"tee": (36.28, -5.33)}, id="salida que no es un punto"),
        pytest.param({"green_center": None}, id="sin green"),
        pytest.param({"tee": None}, id="sin salida"),
    ],
)
def test_g2_an_impossible_line_is_rejected(changes):
    with pytest.raises(InvalidSavedHoleError):
        _save(**changes)


def test_g3_a_point_far_from_the_course_is_rejected():
    with pytest.raises(InvalidSavedHoleError):
        _save(bends=(_north(3100, of=CAMPO),), course_location=CAMPO)


def test_g3_within_three_km_is_fine():
    assert _save(course_location=CAMPO).hole_number == 1


def test_g4_reconstruct_does_not_measure_again():
    hole = SavedHole.reconstruct(
        golf_course_id=GolfCourseId.generate(),
        hole_number=1,
        tee=SALIDA,
        bends=(),
        green_center=_north(10),
        saved_by=UserId.generate(),
        saved_at=datetime(2026, 10, 17, 9, 0),
    )

    assert hole.green_center == _north(10)
