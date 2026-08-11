"""
Tests de la tarjeta por salida: color, metros y rangos por tipo de campo.

Cubre lo que se añadió para poder importar los campos federados de la RFEG:
cada salida lleva su propia tarjeta, porque el par, el índice de dificultad y
la distancia dependen de la barra desde la que se juega.
"""

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]


def build_holes(pars: list[int] | None = None, meters: int | None = 350) -> list[Hole]:
    """Construye una tarjeta de 18 hoyos con índices 1-18."""
    pars = pars or PAR_72
    return [
        Hole(number=i + 1, par=pars[i], stroke_index=i + 1, meters=meters)
        for i in range(18)
    ]


def build_course(
    tees: list[Tee],
    course_type: CourseType = CourseType.STANDARD_18,
    holes: list[Hole] | None = None,
) -> GolfCourse:
    """Crea un campo con las salidas dadas."""
    return GolfCourse.create(
        name="Test Course",
        country_code=CountryCode("ES"),
        course_type=course_type,
        creator_id=UserId.generate(),
        tees=tees,
        holes=holes if holes is not None else build_holes(),
    )


# ============================================================================
# Tests: metros en el hoyo
# ============================================================================


def test_hole_accepts_meters():
    """
    GIVEN: Un hoyo con distancia en metros
    WHEN: Se construye
    THEN: Conserva la distancia
    """
    hole = Hole(number=1, par=4, stroke_index=7, meters=351)

    assert hole.meters == 351


def test_hole_meters_is_optional():
    """
    GIVEN: Un hoyo sin distancia
    WHEN: Se construye
    THEN: La distancia queda a None y el hoyo es válido
    """
    hole = Hole(number=1, par=4, stroke_index=7)

    assert hole.meters is None


def test_hole_rejects_out_of_range_meters():
    """
    GIVEN: Un hoyo con una distancia imposible
    WHEN: Se construye
    THEN: Se lanza ValueError
    """
    with pytest.raises(ValueError, match="Meters must be between"):
        Hole(number=1, par=4, stroke_index=7, meters=1200)


def test_hole_accepts_par_6():
    """
    GIVEN: Un hoyo de par 6
    WHEN: Se construye
    THEN: Es válido

    El hoyo 9 de La Marquesa (644 metros) es par 6 y está federado.
    """
    hole = Hole(number=9, par=6, stroke_index=1, meters=644)

    assert hole.par == 6


def test_hole_rejects_par_7():
    """
    GIVEN: Un hoyo de par 7
    WHEN: Se construye
    THEN: Se lanza ValueError
    """
    with pytest.raises(ValueError, match="Par must be one of"):
        Hole(number=1, par=7, stroke_index=1)


# ============================================================================
# Tests: tarjeta por salida
# ============================================================================


def test_tee_computes_par_and_meters_totals():
    """
    GIVEN: Una salida con su tarjeta completa
    WHEN: Se consultan los totales
    THEN: Se calculan sumando los hoyos
    """
    tee = Tee(
        category=TeeCategory.AMATEUR,
        gender=Gender.MALE,
        color=TeeColor.YELLOW,
        course_rating=71.5,
        slope_rating=126,
        holes=build_holes(meters=350),
    )

    assert tee.par_total == sum(PAR_72)
    assert tee.meters_total == 350 * 18


def test_tee_meters_total_is_none_when_a_hole_lacks_distance():
    """
    GIVEN: Una salida a la que le falta la distancia de un hoyo
    WHEN: Se consulta la distancia total
    THEN: Devuelve None en vez de un total incompleto
    """
    holes = build_holes()
    holes[5].meters = None

    tee = Tee(
        category=TeeCategory.AMATEUR,
        gender=Gender.MALE,
        color=TeeColor.YELLOW,
        course_rating=71.5,
        slope_rating=126,
        holes=holes,
    )

    assert tee.meters_total is None


def test_tees_can_have_different_pars_and_stroke_indices():
    """
    GIVEN: Dos salidas del mismo campo con par e índices distintos
    WHEN: Se crea el campo
    THEN: Cada salida conserva su propia tarjeta

    Ocurre en 77 de los 802 recorridos federados españoles.
    """
    # Given - las blancas tienen un par 5 donde las rojas tienen un par 4, y
    # además los dos primeros hoyos cambian de dificultad entre unas y otras
    pars_white = list(PAR_72)
    pars_red = list(PAR_72)
    pars_red[1] = 4

    red_holes = build_holes(pars_red, meters=300)
    red_holes[0].stroke_index, red_holes[1].stroke_index = (
        red_holes[1].stroke_index,
        red_holes[0].stroke_index,
    )

    white = Tee(
        category=TeeCategory.CHAMPIONSHIP,
        gender=Gender.MALE,
        color=TeeColor.WHITE,
        course_rating=73.5,
        slope_rating=135,
        holes=build_holes(pars_white, meters=400),
    )
    red = Tee(
        category=TeeCategory.FORWARD,
        gender=Gender.FEMALE,
        color=TeeColor.RED,
        course_rating=70.0,
        slope_rating=120,
        holes=red_holes,
    )

    # When
    course = build_course([white, red])

    # Then - cada salida conserva su par, sus metros y sus índices
    assert course.tees[0].par_total == course.tees[1].par_total + 1
    assert course.tees[0].meters_total == 400 * 18
    assert course.tees[1].meters_total == 300 * 18
    assert [h.stroke_index for h in course.tees[0].holes[:2]] == [1, 2]
    assert [h.stroke_index for h in course.tees[1].holes[:2]] == [2, 1]


def test_course_holes_are_propagated_to_tees_without_scorecard():
    """
    GIVEN: Un campo con tarjeta única y salidas sin tarjeta propia
    WHEN: Se crea el campo
    THEN: Cada salida recibe una copia de la tarjeta del campo

    Es lo que mantiene funcionando a quien crea campos como hasta ahora.
    """
    # Given
    tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=73.5,
            slope_rating=135,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.YELLOW,
            course_rating=71.0,
            slope_rating=128,
        ),
    ]

    # When
    course = build_course(tees)

    # Then
    assert all(len(tee.holes) == 18 for tee in course.tees)
    assert course.tees[0].par_total == sum(PAR_72)


def test_course_holes_are_derived_from_first_tee_when_absent():
    """
    GIVEN: Un campo descrito solo con tarjetas por salida
    WHEN: Se crea sin tarjeta de campo
    THEN: La tarjeta de referencia sale de la primera salida

    Así los consumidores que leen golf_course.holes siguen funcionando.
    """
    # Given
    tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=73.5,
            slope_rating=135,
            holes=build_holes(meters=400),
        ),
        Tee(
            category=TeeCategory.FORWARD,
            gender=Gender.FEMALE,
            color=TeeColor.RED,
            course_rating=70.0,
            slope_rating=120,
            holes=build_holes(meters=300),
        ),
    ]

    # When
    course = build_course(tees, holes=[])

    # Then
    assert len(course.holes) == 18
    assert course.total_par == sum(PAR_72)


def test_course_rejects_duplicate_hole_numbers():
    """
    GIVEN: Una tarjeta con números de hoyo repetidos pero índices correctos
    WHEN: Se crea el campo
    THEN: Se lanza ValueError

    La tarjeta de referencia se copia a las salidas asignando la lista, lo que
    no pasa por el validador de Tee. Sin esta comprobación, una tarjeta con
    hoyos repetidos se propagaría a todas las salidas del campo.
    """
    # Given - todos los hoyos son el número 1, pero los índices son 1-18
    holes = [Hole(number=1, par=4, stroke_index=i + 1, meters=350) for i in range(18)]

    # When/Then
    with pytest.raises(ValueError, match="Hole numbers must be exactly"):
        build_course(
            [
                Tee(
                    category=TeeCategory.AMATEUR,
                    gender=Gender.MALE,
                    color=TeeColor.YELLOW,
                    course_rating=71.0,
                    slope_rating=128,
                ),
            ],
            holes=holes,
        )


def test_update_preserves_tee_colors_and_distances():
    """
    GIVEN: Un campo con colores y distancias por salida
    WHEN: Se actualiza
    THEN: Conserva colores, distancias y tarjetas propias

    Al reconstruir las salidas en update() es fácil perder los campos nuevos, y
    una salida de color conocido degradada a OTHER sin identificador ni siquiera
    llegaría a construirse.
    """
    # Given
    white = Tee(
        category=TeeCategory.CHAMPIONSHIP,
        gender=Gender.MALE,
        color=TeeColor.WHITE,
        course_rating=73.5,
        slope_rating=135,
        holes=build_holes(meters=400),
    )
    red = Tee(
        category=TeeCategory.FORWARD,
        gender=Gender.FEMALE,
        color=TeeColor.RED,
        course_rating=70.0,
        slope_rating=120,
        holes=build_holes(meters=300),
    )
    course = build_course([white, red])

    # When
    course.update(
        name="Updated Course",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=[white, red],
        holes=build_holes(meters=400),
    )

    # Then
    assert course.name == "Updated Course"
    assert [tee.color for tee in course.tees] == [TeeColor.WHITE, TeeColor.RED]
    assert course.tees[0].meters_total == 400 * 18
    assert course.tees[1].meters_total == 300 * 18


# ============================================================================
# Tests: unicidad por color
# ============================================================================


def test_two_tees_can_share_category_with_different_colors():
    """
    GIVEN: Dos salidas del mismo campo con la misma categoría y género
    WHEN: Tienen colores distintos
    THEN: El campo es válido

    Un campo puede tener blancas y negras, ambas de campeonato masculino.
    """
    tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.BLACK,
            course_rating=74.5,
            slope_rating=140,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=73.5,
            slope_rating=135,
        ),
    ]

    course = build_course(tees)

    assert len(course.tees) == 2


def test_duplicate_color_and_gender_is_rejected():
    """
    GIVEN: Dos salidas con el mismo color y género
    WHEN: Se crea el campo
    THEN: Se lanza ValueError
    """
    tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=74.5,
            slope_rating=140,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=73.5,
            slope_rating=135,
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate tee"):
        build_course(tees)


def test_tee_with_other_color_requires_identifier():
    """
    GIVEN: Una salida de color OTHER sin identificador
    WHEN: Se construye
    THEN: Se lanza ValueError

    Sin identificador, dos salidas OTHER serían indistinguibles.
    """
    with pytest.raises(ValueError, match="must have an identifier"):
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.OTHER,
            course_rating=71.0,
            slope_rating=128,
        )


# ============================================================================
# Tests: rangos por tipo de campo
# ============================================================================


def test_pitch_and_putt_accepts_low_ratings():
    """
    GIVEN: Un pitch & putt con slope y rating por debajo de la escala WHS
    WHEN: Se crea el campo
    THEN: Es válido

    Arruzafa Golf tiene slope 47 y rating 46,8 desde verdes masculinas.
    """
    tees = [
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.GREEN,
            course_rating=46.8,
            slope_rating=47,
        ),
        Tee(
            category=TeeCategory.FORWARD,
            gender=Gender.FEMALE,
            color=TeeColor.RED,
            course_rating=47.8,
            slope_rating=53,
        ),
    ]

    course = build_course(
        tees,
        course_type=CourseType.PITCH_AND_PUTT,
        holes=build_holes([3] * 18, meters=100),
    )

    assert course.total_par == 54


def test_tee_rejects_impossible_slope():
    """
    GIVEN: Una salida con el slope 11 que la RFEG publica para Golf Xaz
    WHEN: Se construye
    THEN: Se lanza ValueError

    Es la primera barrera: un slope así no es válido en ningún tipo de campo,
    así que lo corta el propio Tee sin necesidad de conocer el tipo.
    """
    with pytest.raises(ValueError, match="Slope rating must be between 40 and 160"):
        Tee(
            category=TeeCategory.FORWARD,
            gender=Gender.MALE,
            color=TeeColor.RED,
            course_rating=63.6,
            slope_rating=11,
        )


def test_standard_course_rejects_pitch_and_putt_slope():
    """
    GIVEN: Un campo estándar con el slope de un pitch & putt
    WHEN: Se crea
    THEN: Se lanza ValueError

    Segunda barrera: 45 es un slope legítimo para un campo corto, pero no para
    uno estándar. Solo el agregado puede juzgarlo, porque es quien conoce el
    tipo de campo.
    """
    tees = [
        Tee(
            category=TeeCategory.FORWARD,
            gender=Gender.MALE,
            color=TeeColor.RED,
            course_rating=63.6,
            slope_rating=45,
        ),
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.YELLOW,
            course_rating=69.3,
            slope_rating=121,
        ),
    ]

    with pytest.raises(ValueError, match="Slope rating for a STANDARD_18"):
        build_course(tees)


def test_standard_course_accepts_slope_above_whs_maximum():
    """
    GIVEN: Un campo estándar con slope 157
    WHEN: Se crea
    THEN: Es válido

    El Real Club de Campo Villa de Madrid publica 157 desde negras de mujeres.
    Rechazarlo por un redondeo ajeno sería perder un campo real.
    """
    tees = [
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.FEMALE,
            color=TeeColor.BLACK,
            course_rating=82.6,
            slope_rating=157,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            color=TeeColor.WHITE,
            course_rating=74.7,
            slope_rating=143,
        ),
    ]

    course = build_course(tees)

    assert course.tees[0].slope_rating == 157


def test_pitch_and_putt_rejects_standard_par():
    """
    GIVEN: Un pitch & putt con par 72
    WHEN: Se crea
    THEN: Se lanza ValueError
    """
    tees = [
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            color=TeeColor.GREEN,
            course_rating=50.0,
            slope_rating=60,
        ),
        Tee(
            category=TeeCategory.FORWARD,
            gender=Gender.FEMALE,
            color=TeeColor.RED,
            course_rating=52.0,
            slope_rating=62,
        ),
    ]

    with pytest.raises(ValueError, match="Total par for a PITCH_AND_PUTT"):
        build_course(tees, course_type=CourseType.PITCH_AND_PUTT)
