"""
Tests del agregado CourseHoleMap: el mapa de los hoyos de un recorrido (BE #532).

Lo importado de OpenStreetMap no se enseña hasta que un admin lo revisa, y lo que
ya revisó no se pisa con una reimportación: esas dos reglas son las que impiden
que a un jugador le lleguen distancias sin mirar.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.user.domain.value_objects.user_id import UserId

IMPORTADO = datetime(2026, 10, 15, 9, 0)
REIMPORTADO = datetime(2026, 11, 2, 9, 0)


def _hole(number: int) -> MappedHole:
    salida = GeoPoint(latitude=36.28 + number / 1000, longitude=-5.33)
    final = GeoPoint(latitude=36.28 + number / 1000, longitude=-5.32)
    return MappedHole(number=number, play_line=(salida, final), line_source=PositionSource.OSM)


def _map(holes: list[MappedHole] | None = None) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=GolfCourseId.generate(),
        holes=holes if holes is not None else [_hole(n) for n in range(1, 19)],
        osm_reference="way/237391513",
        imported_at=IMPORTADO,
    )


# ============================================================================
# M1 — Crear al importar
# ============================================================================


def test_m1_imported_map_is_pending_review():
    """
    GIVEN: Los hoyos emparejados desde OSM
    WHEN: Se crea el mapa
    THEN: Queda pendiente de revisión, con sus hoyos, su referencia OSM y su fecha
    """
    course_id = GolfCourseId.generate()
    holes = [_hole(n) for n in range(1, 19)]

    hole_map = CourseHoleMap.create(
        golf_course_id=course_id,
        holes=holes,
        osm_reference="relation/12345",
        imported_at=IMPORTADO,
    )

    assert hole_map.golf_course_id == course_id
    assert hole_map.status is HoleMapStatus.PENDING_REVIEW
    assert hole_map.holes == tuple(holes)
    assert hole_map.osm_reference == "relation/12345"
    assert hole_map.imported_at == IMPORTADO
    assert hole_map.reviewed_by is None
    assert hole_map.reviewed_at is None
    assert hole_map.rejection_reason is None


def test_m1_holes_are_sorted_by_number():
    """
    GIVEN: Los hoyos en desorden
    WHEN: Se crea el mapa
    THEN: Quedan ordenados por número
    """
    hole_map = _map([_hole(3), _hole(1), _hole(2)])

    assert [hole.number for hole in hole_map.holes] == [1, 2, 3]


@pytest.mark.parametrize("reference", ["", "node/1", "way/", "way/12a", "237391513"])
def test_m1b_osm_reference_must_be_a_way_or_relation(reference):
    """
    GIVEN: Una referencia OSM que no es `way/<id>` ni `relation/<id>`
    WHEN: Se crea el mapa
    THEN: Se rechaza (el contorno de un campo es una vía o una relación)
    """
    with pytest.raises(ValueError, match="OSM reference"):
        CourseHoleMap.create(
            golf_course_id=GolfCourseId.generate(),
            holes=[_hole(1)],
            osm_reference=reference,
            imported_at=IMPORTADO,
        )


# ============================================================================
# M2-M4 — Hoyos del mapa
# ============================================================================


def test_m2_duplicate_hole_numbers_are_rejected():
    """
    GIVEN: Dos hoyos con el mismo número
    WHEN: Se crea el mapa
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="duplicate"):
        _map([_hole(1), _hole(2), _hole(2)])


def test_m3_map_without_holes_is_rejected():
    """
    GIVEN: Ningún hoyo
    WHEN: Se crea el mapa
    THEN: Se rechaza
    """
    with pytest.raises(ValueError, match="at least one hole"):
        _map([])


def test_m4_partial_map_is_allowed():
    """
    GIVEN: 16 de los 18 hoyos
    WHEN: Se crea el mapa
    THEN: Es válido; los dos que faltan se tratan en el front como sin mapear
    """
    hole_map = _map([_hole(n) for n in range(1, 19) if n not in (7, 12)])

    assert len(hole_map.holes) == 16
    assert hole_map.hole(7) is None
    assert hole_map.hole(8) is not None


# ============================================================================
# M5-M7 — Revisión del admin
# ============================================================================


def test_m5_approve_pending_map():
    """
    GIVEN: Un mapa pendiente
    WHEN: Un admin lo aprueba
    THEN: Queda aprobado, con quién y cuándo
    """
    hole_map = _map()
    admin = UserId.generate()

    hole_map.approve(reviewer_id=admin)

    assert hole_map.status is HoleMapStatus.APPROVED
    assert hole_map.reviewed_by == admin
    assert hole_map.reviewed_at is not None
    assert hole_map.rejection_reason is None


def test_m6_reject_pending_map_with_reason():
    """
    GIVEN: Un mapa pendiente
    WHEN: Un admin lo rechaza con un motivo
    THEN: Queda rechazado, con quién, cuándo y el motivo
    """
    hole_map = _map()
    admin = UserId.generate()

    hole_map.reject(reviewer_id=admin, reason="Los greens del 10 al 18 son de otro campo")

    assert hole_map.status is HoleMapStatus.REJECTED
    assert hole_map.reviewed_by == admin
    assert hole_map.reviewed_at is not None
    assert hole_map.rejection_reason == "Los greens del 10 al 18 son de otro campo"


def test_m6_reject_without_reason():
    """
    GIVEN: Un mapa pendiente
    WHEN: Un admin lo rechaza sin motivo
    THEN: Queda rechazado sin motivo (es opcional)
    """
    hole_map = _map()

    hole_map.reject(reviewer_id=UserId.generate())

    assert hole_map.status is HoleMapStatus.REJECTED
    assert hole_map.rejection_reason is None


def test_m6b_blank_reason_is_no_reason():
    """
    GIVEN: Un motivo en blanco
    WHEN: Se rechaza el mapa
    THEN: Se guarda como sin motivo
    """
    hole_map = _map()

    hole_map.reject(reviewer_id=UserId.generate(), reason="   ")

    assert hole_map.rejection_reason is None


def test_m6c_reason_too_long_is_rejected():
    """
    GIVEN: Un motivo de más de 500 caracteres
    WHEN: Se rechaza el mapa
    THEN: Se rechaza la operación y el mapa sigue pendiente
    """
    hole_map = _map()

    with pytest.raises(ValueError, match="500"):
        hole_map.reject(reviewer_id=UserId.generate(), reason="x" * 501)

    assert hole_map.status is HoleMapStatus.PENDING_REVIEW


@pytest.mark.parametrize("first", ["approve", "reject"])
@pytest.mark.parametrize("second", ["approve", "reject"])
def test_m7_reviewed_map_cannot_be_reviewed_again(first, second):
    """
    GIVEN: Un mapa ya aprobado o rechazado
    WHEN: Se intenta aprobar o rechazar de nuevo
    THEN: Se rechaza y no cambia nada
    """
    hole_map = _map()
    admin = UserId.generate()
    getattr(hole_map, first)(reviewer_id=admin)
    status = hole_map.status
    reviewed_at = hole_map.reviewed_at

    with pytest.raises(ValueError, match="pending"):
        getattr(hole_map, second)(reviewer_id=UserId.generate())

    assert hole_map.status is status
    assert hole_map.reviewed_by == admin
    assert hole_map.reviewed_at == reviewed_at
    assert hole_map.rejection_reason is None


# ============================================================================
# M8 — Reimportar
# ============================================================================


def test_m8_reimport_over_pending_replaces_holes():
    """
    GIVEN: Un mapa pendiente
    WHEN: Se reimporta
    THEN: Se sustituyen los hoyos, la referencia y la fecha, y sigue pendiente
    """
    hole_map = _map()

    hole_map.reimport(holes=[_hole(1)], osm_reference="relation/99", imported_at=REIMPORTADO)

    assert [hole.number for hole in hole_map.holes] == [1]
    assert hole_map.osm_reference == "relation/99"
    assert hole_map.imported_at == REIMPORTADO
    assert hole_map.status is HoleMapStatus.PENDING_REVIEW


def test_m8_reimport_over_rejected_goes_back_to_pending():
    """
    GIVEN: Un mapa rechazado
    WHEN: Se reimporta
    THEN: Se sustituyen los hoyos y vuelve a pendiente, sin rastro de la revisión anterior
    """
    hole_map = _map()
    hole_map.reject(reviewer_id=UserId.generate(), reason="Hoyos de otro recorrido")

    hole_map.reimport(holes=[_hole(2)], osm_reference="way/5", imported_at=REIMPORTADO)

    assert hole_map.status is HoleMapStatus.PENDING_REVIEW
    assert [hole.number for hole in hole_map.holes] == [2]
    assert hole_map.reviewed_by is None
    assert hole_map.reviewed_at is None
    assert hole_map.rejection_reason is None


def test_m8_reimport_over_approved_is_rejected():
    """
    GIVEN: Un mapa aprobado
    WHEN: Se intenta reimportar
    THEN: Se rechaza y el mapa revisado no cambia
    """
    hole_map = _map()
    hole_map.approve(reviewer_id=UserId.generate())
    holes = hole_map.holes

    with pytest.raises(ValueError, match="approved"):
        hole_map.reimport(holes=[_hole(1)], osm_reference="way/5", imported_at=REIMPORTADO)

    assert hole_map.holes == holes
    assert hole_map.osm_reference == "way/237391513"
    assert hole_map.status is HoleMapStatus.APPROVED


def test_m8b_reimport_validates_like_create():
    """
    GIVEN: Un mapa pendiente
    WHEN: Se reimporta con hoyos repetidos
    THEN: Se rechaza y el mapa no cambia
    """
    hole_map = _map()
    holes = hole_map.holes

    with pytest.raises(ValueError, match="duplicate"):
        hole_map.reimport(
            holes=[_hole(1), _hole(1)], osm_reference="way/5", imported_at=REIMPORTADO
        )

    assert hole_map.holes == holes
    assert hole_map.osm_reference == "way/237391513"
    assert hole_map.imported_at == IMPORTADO


def test_m8c_reimport_with_bad_reference_changes_nothing():
    """
    GIVEN: Un mapa rechazado
    WHEN: Se reimporta con hoyos válidos pero una referencia OSM inválida
    THEN: Se rechaza y no queda nada a medias: ni hoyos nuevos ni vuelta a pendiente
    """
    hole_map = _map()
    hole_map.reject(reviewer_id=UserId.generate(), reason="Otro recorrido")
    holes = hole_map.holes

    with pytest.raises(ValueError, match="OSM reference"):
        hole_map.reimport(holes=[_hole(1)], osm_reference="node/5", imported_at=REIMPORTADO)

    assert hole_map.holes == holes
    assert hole_map.status is HoleMapStatus.REJECTED
    assert hole_map.rejection_reason == "Otro recorrido"
    assert hole_map.imported_at == IMPORTADO


# ============================================================================
# M9 — Fecha de importación
# ============================================================================


def test_m9_aware_import_date_is_stored_as_naive_utc():
    """
    GIVEN: Una fecha de importación con zona horaria (UTC+2)
    WHEN: Se crea el mapa
    THEN: Se guarda en UTC y sin zona, como el resto de fechas del módulo
         (la columna es `timestamp without time zone`)
    """
    madrid = timezone(timedelta(hours=2))

    hole_map = CourseHoleMap.create(
        golf_course_id=GolfCourseId.generate(),
        holes=[_hole(1)],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 15, 11, 0, tzinfo=madrid),
    )

    assert hole_map.imported_at == datetime(2026, 10, 15, 9, 0)
    assert hole_map.imported_at.tzinfo is None


def test_m9_aware_reimport_date_is_stored_as_naive_utc():
    """
    GIVEN: Un mapa pendiente
    WHEN: Se reimporta con una fecha en UTC con zona
    THEN: Se guarda sin zona
    """
    hole_map = _map()

    hole_map.reimport(
        holes=[_hole(1)], osm_reference="way/1", imported_at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    )

    assert hole_map.imported_at == datetime(2026, 11, 2, 9, 0)
    assert hole_map.imported_at.tzinfo is None
