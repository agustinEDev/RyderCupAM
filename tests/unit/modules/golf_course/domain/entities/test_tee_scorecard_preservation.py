"""
Tests de que editar un campo no borra la tarjeta propia de cada salida.

El formulario de edición es anterior a las tarjetas por barra: manda las
salidas con sus ratings pero sin hoyos. Esa omisión significa "no las toques",
igual que ya pasaba con la ubicación. Sin ello, editar el nombre de un campo
federado le igualaba las cinco barras y le borraba los metros.
"""

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PAR_72 = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]


def build_card(meters: int, stroke_offset: int = 0) -> list[Hole]:
    """Una tarjeta de 18 hoyos con los metros dados, para distinguir barras."""
    return [
        Hole(
            number=i + 1,
            par=PAR_72[i],
            stroke_index=((i + stroke_offset) % 18) + 1,
            meters=meters + i,
        )
        for i in range(18)
    ]


def build_tee(color: TeeColor, gender: Gender, meters: int, identifier: str | None = None) -> Tee:
    """Una salida con tarjeta propia."""
    return Tee(
        gender=gender,
        color=color,
        identifier=identifier,
        course_rating=71.2,
        slope_rating=128,
        holes=build_card(meters),
    )


def build_tee_without_card(
    color: TeeColor, gender: Gender, identifier: str | None = None, slope_rating: int = 128
) -> Tee:
    """Una salida como la manda el formulario de edición: ratings y nada más."""
    return Tee(
        gender=gender,
        color=color,
        identifier=identifier,
        course_rating=71.2,
        slope_rating=slope_rating,
    )


def build_course() -> GolfCourse:
    """Un campo federado con dos barras de distinta longitud, ya aprobado."""
    course = GolfCourse.create(
        name="Real Club de Golf",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            build_tee(TeeColor.YELLOW, Gender.MALE, meters=350),
            build_tee(TeeColor.RED, Gender.FEMALE, meters=290),
        ],
        holes=build_card(350),
    )
    course.approve()
    return course


def edit(course: GolfCourse, tees: list[Tee], name: str = "Real Club de Golf") -> None:
    """Aplica una edición de admin, que es la que va in-place."""
    course.apply_update(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=tees,
        holes=build_card(350),
        is_admin=True,
    )


# ============================================================================
# Tests: la tarjeta de cada salida sobrevive a una edición
# ============================================================================


def test_editing_the_name_keeps_the_metres_of_every_tee():
    """
    GIVEN: Un campo con dos barras de distinta longitud
    WHEN: Un admin edita solo el nombre, mandando las barras sin tarjeta
    THEN: Cada barra conserva sus metros

    Es el caso real: 802 campos federados con hasta 14 barras, y un formulario
    que nunca ha pedido los metros.
    """
    course = build_course()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
        name="Real Club de Golf de Prueba",
    )

    assert course.name == "Real Club de Golf de Prueba"
    yellow = next(tee for tee in course.tees if tee.color is TeeColor.YELLOW)
    red = next(tee for tee in course.tees if tee.color is TeeColor.RED)
    assert [hole.meters for hole in yellow.holes] == [350 + i for i in range(18)]
    assert [hole.meters for hole in red.holes] == [290 + i for i in range(18)]


def test_the_tees_do_not_end_up_identical():
    """
    GIVEN: Un campo con dos barras distintas
    WHEN: Se edita sin mandar tarjetas
    THEN: Las barras siguen siendo distintas entre sí

    El síntoma que se veía era justo ese: todas las barras acababan con la
    misma tarjeta, la de referencia del campo.
    """
    course = build_course()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    cards = {tuple(hole.meters for hole in tee.holes) for tee in course.tees}
    assert len(cards) == 2


def test_a_tee_that_brings_a_card_imposes_it():
    """
    GIVEN: Un campo con dos barras
    WHEN: Se edita mandando una tarjeta nueva para una de ellas
    THEN: Esa barra se queda con la nueva, y la otra con la suya de siempre

    Conservar lo que no se menciona no puede impedir editar lo que sí.
    """
    course = build_course()

    edit(
        course,
        [
            build_tee(TeeColor.YELLOW, Gender.MALE, meters=400),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    yellow = next(tee for tee in course.tees if tee.color is TeeColor.YELLOW)
    red = next(tee for tee in course.tees if tee.color is TeeColor.RED)
    assert yellow.holes[0].meters == 400
    assert red.holes[0].meters == 290


def test_a_brand_new_tee_takes_the_course_card():
    """
    GIVEN: Un campo con dos barras
    WHEN: Se edita añadiendo una barra que no existía, sin tarjeta
    THEN: La nueva hereda la del campo, y las viejas conservan la suya

    Una barra nueva no tiene de dónde heredar, así que se comporta como en un
    alta: la tarjeta del campo es su punto de partida.
    """
    course = build_course()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
            build_tee_without_card(TeeColor.WHITE, Gender.MALE),
        ],
    )

    white = next(tee for tee in course.tees if tee.color is TeeColor.WHITE)
    yellow = next(tee for tee in course.tees if tee.color is TeeColor.YELLOW)
    assert white.holes[0].meters == 350
    assert yellow.holes[0].meters == 350
    assert len(course.tees) == 3


def test_the_gender_is_part_of_the_identity():
    """
    GIVEN: Un campo con una barra amarilla masculina
    WHEN: Se edita mandando una amarilla femenina sin tarjeta
    THEN: No hereda la de la masculina

    El color solo no identifica una salida: el mismo color de barras se juega
    desde distancias distintas según el género.
    """
    course = GolfCourse.create(
        name="Club de Prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            build_tee(TeeColor.YELLOW, Gender.MALE, meters=350),
            build_tee(TeeColor.RED, Gender.FEMALE, meters=290),
        ],
        holes=build_card(500),
    )
    course.approve()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.FEMALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    yellow = next(tee for tee in course.tees if tee.color is TeeColor.YELLOW)
    assert yellow.holes[0].meters == 350


def test_the_identifier_tells_two_other_tees_apart():
    """
    GIVEN: Un campo con dos barras OTHER del mismo género, distinguidas por nombre
    WHEN: Se edita sin mandar tarjetas
    THEN: Cada una conserva la suya

    El color OTHER puede repetirse en un mismo campo, y ahí el nombre es lo
    único que las separa.
    """
    course = GolfCourse.create(
        name="Club de Prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            build_tee(TeeColor.OTHER, Gender.MALE, meters=350, identifier="Championship"),
            build_tee(TeeColor.OTHER, Gender.MALE, meters=300, identifier="Combinadas"),
        ],
        holes=build_card(350),
    )
    course.approve()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.OTHER, Gender.MALE, identifier="Championship"),
            build_tee_without_card(TeeColor.OTHER, Gender.MALE, identifier="Combinadas"),
        ],
    )

    championship = next(tee for tee in course.tees if tee.identifier == "Championship")
    combinadas = next(tee for tee in course.tees if tee.identifier == "Combinadas")
    assert championship.holes[0].meters == 350
    assert combinadas.holes[0].meters == 300


def test_a_change_of_capitalisation_does_not_lose_the_card():
    """
    GIVEN: Una barra identificada como 'Championship'
    WHEN: Se edita mandándola como 'championship', sin tarjeta
    THEN: Conserva la suya

    Si la identidad distinguiera mayúsculas, retocar el nombre de una barra
    la convertiría en nueva y perdería sus metros.
    """
    course = GolfCourse.create(
        name="Club de Prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            build_tee(TeeColor.OTHER, Gender.MALE, meters=350, identifier="Championship"),
            build_tee(TeeColor.RED, Gender.FEMALE, meters=290),
        ],
        holes=build_card(500),
    )
    course.approve()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.OTHER, Gender.MALE, identifier=" championship "),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    other = next(tee for tee in course.tees if tee.color is TeeColor.OTHER)
    assert other.holes[0].meters == 350


# ============================================================================
# Tests: el clon de propuesta también las conserva
# ============================================================================


def test_the_update_proposal_keeps_the_cards_too():
    """
    GIVEN: Un campo aprobado que edita su creador, no un admin
    WHEN: Manda las barras sin tarjeta
    THEN: El clon propuesto conserva los metros de cada barra

    Esa edición no va in-place: crea un clon que un admin aprobará después. Si
    el clon naciera con las tarjetas ya perdidas, aprobarlo las borraría del
    campo de verdad.
    """
    course = build_course()

    clone = course.apply_update(
        name="Real Club de Golf",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        tees=[
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
        holes=build_card(350),
        is_admin=False,
    )

    assert clone is not None
    yellow = next(tee for tee in clone.tees if tee.color is TeeColor.YELLOW)
    red = next(tee for tee in clone.tees if tee.color is TeeColor.RED)
    assert yellow.holes[0].meters == 350
    assert red.holes[0].meters == 290


def test_editing_the_ratings_still_works():
    """
    GIVEN: Un campo con dos barras
    WHEN: Se editan los ratings sin mandar tarjetas
    THEN: Los ratings cambian y las tarjetas siguen intactas

    Conservar la tarjeta no puede congelar el resto de la salida.
    """
    course = build_course()

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE, slope_rating=140),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    yellow = next(tee for tee in course.tees if tee.color is TeeColor.YELLOW)
    assert yellow.slope_rating == 140
    assert yellow.holes[0].meters == 350


@pytest.mark.parametrize("meters", [350, 290])
def test_the_stroke_index_survives_as_well(meters):
    """
    GIVEN: Un campo cuyas barras tienen índices distintos
    WHEN: Se edita sin mandar tarjetas
    THEN: Cada barra conserva su índice

    No solo se perdían los metros: el índice de dificultad por barra caía con
    ellos, y de ese depende el reparto de golpes.
    """
    course = GolfCourse.create(
        name="Club de Prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            Tee(
                gender=Gender.MALE,
                color=TeeColor.YELLOW,
                course_rating=71.2,
                slope_rating=128,
                holes=build_card(350, stroke_offset=0),
            ),
            Tee(
                gender=Gender.FEMALE,
                color=TeeColor.RED,
                course_rating=71.2,
                slope_rating=128,
                holes=build_card(290, stroke_offset=5),
            ),
        ],
        holes=build_card(350),
    )
    course.approve()
    expected = {350: 1, 290: 6}[meters]

    edit(
        course,
        [
            build_tee_without_card(TeeColor.YELLOW, Gender.MALE),
            build_tee_without_card(TeeColor.RED, Gender.FEMALE),
        ],
    )

    tee = next(tee for tee in course.tees if tee.holes[0].meters == meters)
    assert tee.holes[0].stroke_index == expected
