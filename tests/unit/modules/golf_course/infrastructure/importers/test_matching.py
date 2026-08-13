"""
Tests del reconocimiento de campos ya guardados.

Es la parte de la que depende que reimportar actualice en vez de duplicar, y
también la más peligrosa: emparejar mal significa sobrescribir un campo con los
datos de otro. Por eso todo lo que no sea el identificador externo se propone y
lo confirma una persona.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.infrastructure.importers.matching import (
    ExistingCourse,
    MatchKind,
    distance_in_meters,
    find_match,
)
from src.modules.golf_course.infrastructure.importers.rfeg_mapper import map_club

IMPORTED_AT = datetime(2026, 8, 12, 12, 0, 0)
PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]

DERIO_LATITUDE = 43.29519
DERIO_LONGITUDE = -2.87352


def build_card(pars=None):
    """Tarjeta de 18 hoyos."""
    pars = pars or PAR_72
    return [
        {"number": index + 1, "par": pars[index], "stroke_index": index + 1, "meters": 300}
        for index in range(18)
    ]


def build_course(name="PRUEBA - Campo Grande", rfeg_id="915", tees=1, pars=None):
    """Un recorrido ya traducido, listo para emparejar."""
    club = {
        "rfeg_id": rfeg_id,
        "name": "CLUB DE GOLF DE PRUEBA",
        "total_holes": 18,
        "latitude": DERIO_LATITUDE,
        "longitude": DERIO_LONGITUDE,
        "place": "DERIO",
        "province": "VIZCAYA",
        "courses": [
            {
                "name": name,
                "tees": [
                    {
                        "color": color,
                        "gender": "M",
                        "course_rating": 71.2,
                        "slope_rating": 128,
                        "holes": build_card(pars),
                    }
                    for color in ["AMARILLAS", "BLANCAS", "ROJAS"][:tees]
                ],
            }
        ],
    }
    return map_club(club, IMPORTED_AT)[0]


def build_existing(
    name="Prueba - Campo Grande",
    source=CourseSource.RFEG,
    external_id="915:PRUEBA CAMPO GRANDE",
    latitude=DERIO_LATITUDE,
    longitude=DERIO_LONGITUDE,
    total_par=72,
    tee_count=1,
):
    """Un campo ya guardado."""
    return ExistingCourse(
        id="11111111-1111-1111-1111-111111111111",
        name=name,
        source=source,
        external_id=external_id,
        latitude=latitude,
        longitude=longitude,
        total_par=total_par,
        tee_count=tee_count,
    )


# ============================================================================
# Tests: coincidencia exacta
# ============================================================================


def test_the_same_external_id_is_an_exact_match():
    """
    GIVEN: Un campo ya importado con el mismo identificador externo
    WHEN: Se busca su correspondencia
    THEN: Se reconoce sin necesidad de confirmación
    """
    match = find_match(build_course(), [build_existing()])

    assert match.kind is MatchKind.EXACT
    assert match.needs_confirmation is False


def test_an_empty_database_gives_a_new_course():
    """
    GIVEN: Ningún campo guardado
    WHEN: Se busca la correspondencia
    THEN: Es un campo nuevo
    """
    match = find_match(build_course(), [])

    assert match.kind is MatchKind.NEW


def test_a_course_of_another_club_is_not_a_match():
    """
    GIVEN: Un campo guardado de otro club con la misma forma de tarjeta
    WHEN: Se busca la correspondencia
    THEN: No se empareja
    """
    match = find_match(build_course(), [build_existing(external_id="777:OTRO CAMPO")])

    assert match.kind is MatchKind.NEW


# ============================================================================
# Tests: renombrados por la federación
# ============================================================================


def test_a_renamed_course_is_recognised_but_needs_confirmation():
    """
    GIVEN: Un campo del mismo club, con la misma tarjeta y otro identificador
    WHEN: Se busca la correspondencia
    THEN: Se propone como renombrado, pendiente de que alguien lo confirme

    Es lo que evita duplicar un campo porque la federación le cambió el nombre.
    """
    existing = build_existing(
        name="Prueba - Nombre Viejo", external_id="915:PRUEBA NOMBRE VIEJO"
    )

    match = find_match(build_course(), [existing])

    assert match.kind is MatchKind.RENAMED
    assert match.needs_confirmation is True
    assert match.existing is existing


def test_a_different_course_of_the_same_club_is_not_a_rename():
    """
    GIVEN: Otro recorrido del mismo club, con distinto par
    WHEN: Se busca la correspondencia
    THEN: No se empareja: un club tiene varios campos y son distintos

    Sin comparar la tarjeta, el pitch & putt de un club se emparejaría con su
    campo grande, que comparte club y coordenadas.
    """
    existing = build_existing(external_id="915:PRUEBA P Y P", total_par=54)

    match = find_match(build_course(), [existing])

    assert match.kind is MatchKind.NEW


def test_two_candidates_of_the_same_club_are_too_ambiguous():
    """
    GIVEN: Dos campos del mismo club con la misma forma de tarjeta
    WHEN: Se busca la correspondencia
    THEN: Se trata como campo nuevo

    Duplicar tiene arreglo; sobrescribir el campo equivocado, no.
    """
    first = build_existing(name="Uno", external_id="915:UNO")
    second = build_existing(name="Dos", external_id="915:DOS")

    match = find_match(build_course(), [first, second])

    assert match.kind is MatchKind.NEW


# ============================================================================
# Tests: campos dados de alta a mano
# ============================================================================


def test_a_hand_created_course_with_the_same_name_is_proposed():
    """
    GIVEN: Un campo creado a mano que se llama igual
    WHEN: Se busca la correspondencia
    THEN: Se propone para fusionar, pendiente de confirmación
    """
    existing = build_existing(source=CourseSource.MANUAL, external_id=None)

    match = find_match(build_course(), [existing])

    assert match.kind is MatchKind.MANUAL
    assert match.needs_confirmation is True


def test_a_hand_created_course_next_door_with_the_same_card_is_proposed():
    """
    GIVEN: Un campo creado a mano con otro nombre, al lado y con la misma tarjeta
    WHEN: Se busca la correspondencia
    THEN: Se propone: es casi seguro el mismo campo escrito de otra forma
    """
    existing = build_existing(
        name="Campo del pueblo",
        source=CourseSource.MANUAL,
        external_id=None,
        latitude=DERIO_LATITUDE + 0.001,
        longitude=DERIO_LONGITUDE,
    )

    match = find_match(build_course(), [existing])

    assert match.kind is MatchKind.MANUAL


def test_a_hand_created_course_far_away_is_not_proposed():
    """
    GIVEN: Un campo creado a mano con otro nombre y lejos
    WHEN: Se busca la correspondencia
    THEN: No se empareja, aunque la tarjeta coincida
    """
    existing = build_existing(
        name="Campo de otra provincia",
        source=CourseSource.MANUAL,
        external_id=None,
        latitude=40.4,
        longitude=-3.7,
    )

    match = find_match(build_course(), [existing])

    assert match.kind is MatchKind.NEW


def test_several_similar_hand_created_courses_are_left_alone():
    """
    GIVEN: Dos campos creados a mano que se parecen al importado
    WHEN: Se busca la correspondencia
    THEN: No se fusiona ninguno y se explica por qué
    """
    first = build_existing(source=CourseSource.MANUAL, external_id=None, name="Prueba Campo Grande")
    second = build_existing(
        source=CourseSource.MANUAL,
        external_id=None,
        name="Prueba - Campo Grande",
        latitude=DERIO_LATITUDE + 0.0005,
    )

    match = find_match(build_course(), [first, second])

    assert match.kind is MatchKind.NEW
    assert "ambiguous" in match.reason


# ============================================================================
# Tests: distancia
# ============================================================================


def test_distance_between_the_same_point_is_zero():
    """
    GIVEN: Dos veces el mismo punto
    WHEN: Se mide la distancia
    THEN: Es cero
    """
    assert distance_in_meters(43.0, -2.0, 43.0, -2.0) == pytest.approx(0.0)


def test_a_degree_of_latitude_is_about_111_kilometres():
    """
    GIVEN: Dos puntos separados por un grado de latitud
    WHEN: Se mide la distancia
    THEN: Ronda los 111 kilómetros, que es la referencia conocida
    """
    assert distance_in_meters(43.0, -2.0, 44.0, -2.0) == pytest.approx(111_195, rel=0.01)
