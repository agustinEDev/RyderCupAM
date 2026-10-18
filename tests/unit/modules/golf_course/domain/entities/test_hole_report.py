"""
Tests del reporte de un hoyo (entrega 7, aprobada por Agustín el 18 oct 2026).

Un jugador ve un hoyo mal y lo reporta: un motivo y la línea que propone
(salida, hasta dos codos y centro del green). Como las muestras, no guarda
quién lo mandó y de cuándo llegó solo el día (UTC); el id lo pone el móvil.

| Caso | Situación                                         | Resultado                                  |
|------|---------------------------------------------------|--------------------------------------------|
| B1   | Motivo y línea con dos codos, green a 300 m       | Se crea, con el id del móvil y el día UTC  |
| B2   | Los tres motivos                                  | WRONG_HOLE, WRONG_LINE y HOLE_CHANGED       |
| B3   | Motivo que no es del enum                         | InvalidHoleReportError                     |
| B4   | Sin salida                                        | InvalidHoleReportError (siempre línea)     |
| B5   | Tres codos                                        | InvalidHoleReportError                     |
| B6   | Hoyo 0 o 19, o un número que no es entero         | InvalidHoleReportError                     |
| B7   | Green a 30 m o a 800 m de la salida               | InvalidHoleReportError                     |
| B8   | Un punto a más de 3 km del campo                  | InvalidHoleReportError                     |
| B9   | Campo sin ubicación                               | No se mira la distancia al campo           |
| B10  | Leído de la BD (`reconstruct`)                    | No se vuelven a medir distancias           |
| B11  | Un datetime como día, o un id que no es UUID      | InvalidHoleReportError                     |
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.hole_report import (
    MAX_REPORTS_PER_HOLE,
    HoleReport,
    HoleReportReason,
    InvalidHoleReportError,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CAMPO = GeoPoint(latitude=36.285, longitude=-5.33)


def _north(metres: float, of: GeoPoint = SALIDA) -> GeoPoint:
    return GeoPoint(latitude=of.latitude + metres / M_PER_DEGREE, longitude=of.longitude)


def _create(**overrides):
    datos = {
        "id": uuid4(),
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 7,
        "reason": HoleReportReason.WRONG_LINE,
        "tee": SALIDA,
        "bends": [_north(100), _north(200)],
        "green_center": _north(300),
        "course_location": CAMPO,
    }
    datos.update(overrides)
    return HoleReport.create(**datos)


def test_b1_creates_a_report_with_the_phone_id_and_the_utc_day():
    """
    GIVEN: Un motivo y una línea con dos codos y el green a 300 m
    WHEN: Se crea el reporte
    THEN: Lleva el id del móvil, el hoyo, el motivo, la línea y solo el día UTC
    """
    report_id = uuid4()
    course_id = GolfCourseId.generate()

    report = _create(id=report_id, golf_course_id=course_id, reason=HoleReportReason.WRONG_HOLE)

    assert report.id == report_id
    assert report.golf_course_id == course_id
    assert report.hole_number == 7
    assert report.reason is HoleReportReason.WRONG_HOLE
    assert report.tee == SALIDA
    assert report.bends == (_north(100), _north(200))
    assert report.green_center == _north(300)
    assert report.received_on == datetime.now(UTC).date()
    assert type(report.received_on) is date
    assert MAX_REPORTS_PER_HOLE == 3


def test_b2_the_three_reasons():
    """
    GIVEN: Los motivos del menú
    WHEN: Se miran sus valores
    THEN: Son los tres aprobados, y cada uno crea un reporte
    """
    assert {r.value for r in HoleReportReason} == {"WRONG_HOLE", "WRONG_LINE", "HOLE_CHANGED"}
    for reason in HoleReportReason:
        assert _create(reason=reason).reason is reason


def test_b3_a_reason_outside_the_enum_is_rejected():
    """
    GIVEN: Un motivo que es un texto, no el enum
    WHEN: Se crea
    THEN: InvalidHoleReportError
    """
    with pytest.raises(InvalidHoleReportError):
        _create(reason="WRONG_LINE")


def test_b4_a_report_always_brings_a_tee():
    """
    GIVEN: Un reporte sin salida
    WHEN: Se crea
    THEN: InvalidHoleReportError: la línea propuesta es entera
    """
    with pytest.raises(InvalidHoleReportError):
        _create(tee=None, bends=[])


def test_b5_at_most_two_bends():
    """
    GIVEN: Tres codos
    WHEN: Se crea
    THEN: InvalidHoleReportError
    """
    with pytest.raises(InvalidHoleReportError):
        _create(bends=[_north(50), _north(100), _north(150)])


@pytest.mark.parametrize("hole", [0, 19, 7.0, True, "7"])
def test_b6_hole_must_be_an_int_from_1_to_18(hole):
    """
    GIVEN: Un hoyo fuera de 1-18, o que no es un entero
    WHEN: Se crea
    THEN: InvalidHoleReportError
    """
    with pytest.raises(InvalidHoleReportError):
        _create(hole_number=hole)


@pytest.mark.parametrize("metres", [30, 800])
def test_b7_green_must_be_40_to_750_m_from_the_tee(metres):
    """
    GIVEN: El green a 30 m o a 800 m de la salida
    WHEN: Se crea
    THEN: InvalidHoleReportError
    """
    with pytest.raises(InvalidHoleReportError):
        _create(bends=[], green_center=_north(metres))


@pytest.mark.parametrize("metres", [40.5, 749.5])
def test_b7_the_edges_are_valid(metres):
    """
    GIVEN: El green justo dentro de 40 m y de 750 m
    WHEN: Se crea
    THEN: Se crea
    """
    assert _create(bends=[], green_center=_north(metres), course_location=None)


def test_b8_a_point_more_than_3_km_from_the_course_is_rejected():
    """
    GIVEN: Un codo a más de 3 km del campo
    WHEN: Se crea
    THEN: InvalidHoleReportError
    """
    with pytest.raises(InvalidHoleReportError):
        _create(bends=[_north(5000)], green_center=_north(300))


def test_b9_without_course_location_the_distance_to_it_is_not_checked():
    """
    GIVEN: Una línea lejos de donde estaría el campo, y el campo sin ubicación
    WHEN: Se crea
    THEN: Se crea
    """
    lejos = GeoPoint(latitude=40.0, longitude=-3.7)

    report = _create(tee=lejos, bends=[], green_center=_north(300, of=lejos), course_location=None)

    assert report.tee == lejos


def test_b10_reconstruct_does_not_measure_again():
    """
    GIVEN: Un reporte leído de la BD con el green a 10 m (los límites cambiaron)
    WHEN: Se reconstruye
    THEN: Se carga igual, con su día
    """
    report = HoleReport.reconstruct(
        id=uuid4(),
        golf_course_id=GolfCourseId.generate(),
        hole_number=3,
        reason=HoleReportReason.HOLE_CHANGED,
        tee=SALIDA,
        bends=[],
        green_center=_north(10),
        received_on=date(2026, 10, 18),
    )

    assert report.received_on == date(2026, 10, 18)
    assert report.play_line == (SALIDA, _north(10))


@pytest.mark.parametrize(
    "overrides",
    [
        {"received_on": datetime(2026, 10, 18, 9, 0)},
        {"id": "no-es-un-uuid"},
    ],
    ids=["datetime", "id"],
)
def test_b11_the_day_has_no_time_and_the_id_is_a_uuid(overrides):
    """
    GIVEN: Un datetime como día, o un id que no es un UUID
    WHEN: Se reconstruye
    THEN: InvalidHoleReportError
    """
    datos = {
        "id": uuid4(),
        "golf_course_id": GolfCourseId.generate(),
        "hole_number": 3,
        "reason": HoleReportReason.WRONG_LINE,
        "tee": SALIDA,
        "bends": [],
        "green_center": _north(300),
        "received_on": date(2026, 10, 18),
    }
    datos.update(overrides)
    with pytest.raises(InvalidHoleReportError):
        HoleReport.reconstruct(**datos)
