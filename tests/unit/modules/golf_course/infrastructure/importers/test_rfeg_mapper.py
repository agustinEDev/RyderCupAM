"""
Tests de la traducción de un recorrido federado a una petición del backend.

Se comprueba sobre todo lo que la fuente no dice explícitamente y hay que
deducir: el tipo de campo, si el recorrido es de nueve hoyos, y el
identificador con el que se le reconocerá en la siguiente importación.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.importers.rfeg_mapper import (
    RfegMappingError,
    build_external_id,
    detect_course_type,
    detect_physical_holes,
    map_club,
    map_club_courses,
)

IMPORTED_AT = datetime(2026, 8, 12, 12, 0, 0)

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
PAR_54 = [3] * 18


def build_card(pars=None, meters_front=None, meters_back=None):
    """Construye la tarjeta de 18 hoyos de una salida."""
    pars = pars or PAR_72
    meters_front = meters_front or list(range(100, 190, 10))
    meters_back = meters_back if meters_back is not None else list(range(200, 290, 10))
    meters = meters_front + meters_back
    return [
        {"number": index + 1, "par": pars[index], "stroke_index": index + 1, "meters": meters[index]}
        for index in range(18)
    ]


def build_club(courses=None, total_holes=18, **overrides):
    """Construye un club del volcado."""
    club = {
        "rfeg_id": "915",
        "name": "CLUB DE GOLF DE PRUEBA",
        "total_holes": total_holes,
        "latitude": 43.29519,
        "longitude": -2.87352,
        "address": "CALLE EREAGA BIDEA S/N, DERIO",
        "place": "DERIO",
        "province": "VIZCAYA",
        "courses": courses
        if courses is not None
        else [
            {
                "name": "PRUEBA - Campo Grande",
                "tees": [
                    {
                        "color": "AMARILLAS",
                        "gender": "M",
                        "course_rating": 71.2,
                        "slope_rating": 128,
                        "holes": build_card(),
                    }
                ],
            }
        ],
    }
    club.update(overrides)
    return club


# ============================================================================
# Tests: traducción completa
# ============================================================================


def test_a_course_becomes_a_valid_request():
    """
    GIVEN: Un club con un recorrido
    WHEN: Se traduce
    THEN: Sale una petición con su nombre, tipo, salidas y ubicación
    """
    mapped = map_club(build_club(), IMPORTED_AT)

    assert len(mapped) == 1
    request = mapped[0].request
    assert request.name == "Prueba - Campo Grande"
    assert request.country_code == "ES"
    assert request.course_type is CourseType.STANDARD_18
    assert len(request.tees) == 1
    assert request.tees[0].color is TeeColor.YELLOW
    assert request.tees[0].tee_gender == "MALE"
    assert len(request.holes) == 18
    assert request.location is not None
    assert request.location.city == "Derio"
    assert request.location.province == "Vizcaya"


def test_the_provenance_marks_it_as_federated():
    """
    GIVEN: Un recorrido traducido
    WHEN: Se mira su procedencia
    THEN: Consta como importado de la RFEG, con su fecha
    """
    mapped = map_club(build_club(), IMPORTED_AT)

    provenance = mapped[0].provenance
    assert provenance.source is CourseSource.RFEG
    assert provenance.imported_at == IMPORTED_AT
    assert provenance.external_id == "915:PRUEBA CAMPO GRANDE"


def test_a_club_without_coordinates_still_maps():
    """
    GIVEN: Un club sin coordenadas, como 11 de los 442 federados
    WHEN: Se traduce
    THEN: El campo se importa igual, con localidad pero sin coordenadas
    """
    mapped = map_club(build_club(latitude=None, longitude=None), IMPORTED_AT)

    location = mapped[0].request.location
    assert location is not None
    assert location.latitude is None
    assert location.city == "Derio"


def test_half_a_coordinate_is_discarded():
    """
    GIVEN: Un club con latitud pero sin longitud
    WHEN: Se traduce
    THEN: Se descartan las dos, porque media coordenada no sitúa nada
    """
    mapped = map_club(build_club(longitude=None), IMPORTED_AT)

    location = mapped[0].request.location
    assert location is not None
    assert location.latitude is None
    assert location.longitude is None


# ============================================================================
# Tests: identificador externo
# ============================================================================


def test_the_external_id_ignores_accents_and_case():
    """
    GIVEN: El mismo recorrido escrito con distinta capitalización o tildes
    WHEN: Se compone su identificador
    THEN: Sale el mismo

    Es lo que evita que cambiar nuestra tabla de tildes convierta los 802
    campos en desconocidos en la siguiente importación.
    """
    club = build_club()

    assert build_external_id(club, "ALHAURIN - P&P") == build_external_id(club, "Alhaurín  p&p")


# ============================================================================
# Tests: tipo de campo
# ============================================================================


@pytest.mark.parametrize(
    "total_par,expected",
    [(54, CourseType.PITCH_AND_PUTT), (60, CourseType.PITCH_AND_PUTT),
     (61, CourseType.EXECUTIVE), (65, CourseType.EXECUTIVE),
     (66, CourseType.STANDARD_18), (72, CourseType.STANDARD_18), (76, CourseType.STANDARD_18)],
)
def test_the_type_comes_from_the_total_par(total_par, expected):
    """
    GIVEN: Un par total
    WHEN: Se deduce el tipo de campo
    THEN: Sale el que corresponde a ese rango
    """
    assert detect_course_type(total_par) is expected


@pytest.mark.parametrize("impossible_par", [40, 53, 77, 90])
def test_an_impossible_par_is_rejected(impossible_par):
    """
    GIVEN: Un par total fuera de todo rango conocido
    WHEN: Se deduce el tipo
    THEN: Falla, en vez de inventarse un tipo
    """
    with pytest.raises(RfegMappingError, match="does not match any course type"):
        detect_course_type(impossible_par)


def test_a_pitch_and_putt_is_recognised():
    """
    GIVEN: Un recorrido de par 54
    WHEN: Se traduce
    THEN: Se da de alta como pitch & putt
    """
    club = build_club(
        courses=[
            {
                "name": "PRUEBA - P&P",
                "tees": [
                    {
                        "color": "VERDES",
                        "gender": "F",
                        "course_rating": 52.6,
                        "slope_rating": 62,
                        "holes": build_card(pars=PAR_54),
                    }
                ],
            }
        ]
    )

    mapped = map_club(club, IMPORTED_AT)

    assert mapped[0].request.course_type is CourseType.PITCH_AND_PUTT


# ============================================================================
# Tests: hoyos físicos
# ============================================================================


def test_a_nine_hole_club_is_marked_as_nine():
    """
    GIVEN: Un club que la federación declara de nueve hoyos
    WHEN: Se traduce su recorrido
    THEN: Queda marcado como de nueve, aunque la tarjeta tenga 18
    """
    assert detect_physical_holes(build_club(total_holes=9), build_card()) == 9


def test_a_repeated_round_is_marked_as_nine():
    """
    GIVEN: Un recorrido cuyas dos vueltas son idénticas en par y metros
    WHEN: Se mira cuántos hoyos tiene sobre el terreno
    THEN: Son nueve, aunque el club sea de 18 o 27

    Es el caso de los 148 pitch & putt anexos a campos grandes.
    """
    front = [3] * 9
    meters = list(range(100, 190, 10))
    card = build_card(pars=front + front, meters_front=meters, meters_back=meters)

    assert detect_physical_holes(build_club(total_holes=27), card) == 9


def test_an_eighteen_hole_course_is_marked_as_eighteen():
    """
    GIVEN: Un recorrido con dos vueltas distintas en un club de 18
    WHEN: Se mira cuántos hoyos tiene
    THEN: Son dieciocho
    """
    assert detect_physical_holes(build_club(total_holes=18), build_card()) == 18


def test_a_nine_hole_club_playing_different_tees_is_still_nine():
    """
    GIVEN: Un club de nueve hoyos cuya segunda vuelta se juega desde otras barras
    WHEN: Se mira cuántos hoyos tiene
    THEN: Siguen siendo nueve, gracias al dato del club

    Son 83 recorridos que la repetición por sí sola no detecta.
    """
    card = build_card(meters_front=list(range(100, 190, 10)), meters_back=list(range(120, 210, 10)))

    assert detect_physical_holes(build_club(total_holes=9), card) == 9


# ============================================================================
# Tests: datos que no se pueden traducir
# ============================================================================


def test_an_unknown_colour_stops_the_course():
    """
    GIVEN: Una salida con un color que no está entre los nueve conocidos
    WHEN: Se traduce
    THEN: Falla: significa que la fuente ha cambiado y hay que mirarlo
    """
    club = build_club(
        courses=[
            {
                "name": "PRUEBA - Raro",
                "tees": [
                    {
                        "color": "MORADAS",
                        "gender": "M",
                        "course_rating": 71.2,
                        "slope_rating": 128,
                        "holes": build_card(),
                    }
                ],
            }
        ]
    )

    with pytest.raises(RfegMappingError, match="Unknown tee colour"):
        map_club(club, IMPORTED_AT)


def test_an_unknown_gender_stops_the_course():
    """
    GIVEN: Una salida con un género que no es M ni F
    WHEN: Se traduce
    THEN: Falla
    """
    club = build_club(
        courses=[
            {
                "name": "PRUEBA - Raro",
                "tees": [
                    {
                        "color": "ROJAS",
                        "gender": "X",
                        "course_rating": 71.2,
                        "slope_rating": 128,
                        "holes": build_card(),
                    }
                ],
            }
        ]
    )

    with pytest.raises(RfegMappingError, match="Unknown tee gender"):
        map_club(club, IMPORTED_AT)


def test_a_course_without_tees_stops():
    """
    GIVEN: Un recorrido sin ninguna salida
    WHEN: Se traduce
    THEN: Falla, porque no habría con qué jugar
    """
    with pytest.raises(RfegMappingError, match="has no tees"):
        map_club(build_club(courses=[{"name": "PRUEBA - Vacio", "tees": []}]), IMPORTED_AT)


def test_a_short_scorecard_stops():
    """
    GIVEN: Una salida con menos de 18 hoyos
    WHEN: Se traduce
    THEN: Falla
    """
    club = build_club(
        courses=[
            {
                "name": "PRUEBA - Corto",
                "tees": [
                    {
                        "color": "ROJAS",
                        "gender": "F",
                        "course_rating": 71.2,
                        "slope_rating": 128,
                        "holes": build_card()[:9],
                    }
                ],
            }
        ]
    )

    with pytest.raises(RfegMappingError, match="must have 18 holes"):
        map_club(club, IMPORTED_AT)


# ============================================================================
# Tests: aislar el recorrido que falla
# ============================================================================


GOOD_COURSE = {
    "name": "PRUEBA - Campo Grande",
    "tees": [
        {
            "color": "AMARILLAS",
            "gender": "M",
            "course_rating": 71.2,
            "slope_rating": 128,
            "holes": build_card(),
        }
    ],
}
BROKEN_COURSE = {"name": "PRUEBA - Vacio", "tees": []}
INVALID_COURSE = {
    "name": "PRUEBA - Slope Imposible",
    "tees": [
        {
            "color": "ROJAS",
            "gender": "F",
            "course_rating": 71.2,
            "slope_rating": 9999,
            "holes": build_card(),
        }
    ],
}


def test_a_broken_course_does_not_drag_down_the_rest_of_the_club():
    """
    GIVEN: Un club con un recorrido bueno y otro sin salidas
    WHEN: Se traducen aislando los fallos
    THEN: Sale el bueno y se informa solo del malo

    Es la diferencia con map_club: un club de dos recorridos no debe perder el
    que sí se puede importar por culpa del que no.
    """
    club = build_club(courses=[GOOD_COURSE, BROKEN_COURSE])

    mapped, problems = map_club_courses(club, IMPORTED_AT)

    assert len(mapped) == 1
    assert mapped[0].source_course_name == "PRUEBA - Campo Grande"
    assert len(problems) == 1
    assert "PRUEBA - Vacio" in problems[0]
    assert "has no tees" in problems[0]


def test_a_course_the_dtos_reject_does_not_drag_down_the_rest():
    """
    GIVEN: Un club con un recorrido de slope imposible y otro correcto
    WHEN: Se traducen aislando los fallos
    THEN: Sale el bueno y se informa del que rechazan los DTO

    Los DTO son de Pydantic y su ValidationError es un ValueError, no un
    RfegMappingError. Sin recogerlo, un solo rating fuera de rango no se
    llevaba por delante su club: se escapaba hasta arriba y tumbaba la
    importación entera.
    """
    club = build_club(courses=[INVALID_COURSE, GOOD_COURSE])

    mapped, problems = map_club_courses(club, IMPORTED_AT)

    assert len(mapped) == 1
    assert mapped[0].source_course_name == "PRUEBA - Campo Grande"
    assert len(problems) == 1
    assert "PRUEBA - Slope Imposible" in problems[0]
    assert "slope_rating" in problems[0]


def test_the_problem_names_the_club_and_the_course():
    """
    GIVEN: Un club cuyo único recorrido no se puede traducir
    WHEN: Se traduce aislando los fallos
    THEN: El aviso nombra al club y al recorrido, para poder localizarlo
    """
    club = build_club(courses=[BROKEN_COURSE])

    mapped, problems = map_club_courses(club, IMPORTED_AT)

    assert mapped == []
    assert problems == [
        "CLUB DE GOLF DE PRUEBA / PRUEBA - Vacio: Course 'PRUEBA - Vacio' has no tees"
    ]


def test_a_club_without_problems_reports_none():
    """
    GIVEN: Un club cuyos recorridos se traducen todos
    WHEN: Se traduce aislando los fallos
    THEN: Salen los recorridos y ningún aviso
    """
    mapped, problems = map_club_courses(build_club(), IMPORTED_AT)

    assert len(mapped) == 1
    assert problems == []


def test_a_club_that_cannot_be_prepared_still_raises():
    """
    GIVEN: Un club con un recorrido sin nombre
    WHEN: Se traduce aislando los fallos
    THEN: Falla, porque los nombres se calculan para el club entero

    Aislar por recorrido no puede empezar hasta tener los nombres, que dependen
    unos de otros. Un fallo ahí sí se lleva el club por delante.
    """
    with pytest.raises(KeyError):
        map_club_courses(build_club(courses=[{"tees": []}]), IMPORTED_AT)
