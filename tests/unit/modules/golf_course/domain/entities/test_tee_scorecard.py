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
        color=TeeColor.YELLOW,
        gender=Gender.MALE,
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
        color=TeeColor.YELLOW,
        gender=Gender.MALE,
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
        color=TeeColor.WHITE,
        gender=Gender.MALE,
        course_rating=73.5,
        slope_rating=135,
        holes=build_holes(pars_white, meters=400),
    )
    red = Tee(
        color=TeeColor.RED,
        gender=Gender.FEMALE,
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
            color=TeeColor.WHITE,
            gender=Gender.MALE,
            course_rating=73.5,
            slope_rating=135,
        ),
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
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

    Así los consumidores que leen golf_course.reference_card siguen funcionando.
    """
    # Given
    tees = [
        Tee(
            color=TeeColor.WHITE,
            gender=Gender.MALE,
            course_rating=73.5,
            slope_rating=135,
            holes=build_holes(meters=400),
        ),
        Tee(
            color=TeeColor.RED,
            gender=Gender.FEMALE,
            course_rating=70.0,
            slope_rating=120,
            holes=build_holes(meters=300),
        ),
    ]

    # When
    course = build_course(tees, holes=[])

    # Then
    assert len(course.reference_card) == 18
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
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
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
        color=TeeColor.WHITE,
        gender=Gender.MALE,
        course_rating=73.5,
        slope_rating=135,
        holes=build_holes(meters=400),
    )
    red = Tee(
        color=TeeColor.RED,
        gender=Gender.FEMALE,
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
            gender=Gender.MALE,
            color=TeeColor.BLACK,
            course_rating=74.5,
            slope_rating=140,
        ),
        Tee(
            color=TeeColor.WHITE,
            gender=Gender.MALE,
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
            color=TeeColor.WHITE,
            gender=Gender.MALE,
            course_rating=74.5,
            slope_rating=140,
        ),
        Tee(
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
            gender=Gender.MALE,
            color=TeeColor.GREEN,
            course_rating=46.8,
            slope_rating=47,
        ),
        Tee(
            color=TeeColor.RED,
            gender=Gender.FEMALE,
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
            color=TeeColor.RED,
            gender=Gender.MALE,
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
            color=TeeColor.RED,
            gender=Gender.MALE,
            course_rating=63.6,
            slope_rating=45,
        ),
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
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
            gender=Gender.FEMALE,
            color=TeeColor.BLACK,
            course_rating=82.6,
            slope_rating=157,
        ),
        Tee(
            color=TeeColor.WHITE,
            gender=Gender.MALE,
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
            gender=Gender.MALE,
            color=TeeColor.GREEN,
            course_rating=50.0,
            slope_rating=60,
        ),
        Tee(
            color=TeeColor.RED,
            gender=Gender.FEMALE,
            course_rating=52.0,
            slope_rating=62,
        ),
    ]

    with pytest.raises(ValueError, match="Total par for a PITCH_AND_PUTT"):
        build_course(tees, course_type=CourseType.PITCH_AND_PUTT)


class TestHoleCardFor:
    """
    Tarjeta que juega cada salida.

    El par, el índice y los metros son de la barra: `reference_card` es solo la
    derivada de la primera que tenga tarjeta. Resolver la barra estaba copiado
    en los dos context builders y en el frontend; vive aquí para que haya una
    sola respuesta a "qué tarjeta juega este jugador".
    """

    @staticmethod
    def _course_with_two_cards() -> GolfCourse:
        """Amarillas y rojas con par e índice distintos en el hoyo 1."""
        yellow_pars = list(PAR_72)
        red_pars = list(PAR_72)
        red_pars[0] = 5  # el 1 juega par 5 desde rojas y par 4 desde amarillas
        return build_course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=71.0,
                    slope_rating=128,
                    holes=build_holes(yellow_pars, meters=350),
                ),
                Tee(
                    color=TeeColor.RED,
                    gender=Gender.FEMALE,
                    course_rating=73.0,
                    slope_rating=131,
                    holes=build_holes(red_pars, meters=300),
                ),
            ]
        )

    def test_devuelve_la_tarjeta_de_esa_salida(self) -> None:
        course = self._course_with_two_cards()

        yellow = course.hole_card_for(TeeColor.YELLOW, Gender.MALE)
        red = course.hole_card_for(TeeColor.RED, Gender.FEMALE)

        assert yellow[0].par == 4
        assert red[0].par == 5
        assert yellow[0].meters == 350
        assert red[0].meters == 300

    def test_reserva_a_la_salida_sin_genero(self) -> None:
        """
        El jugador siempre manda color y género; un campo dado de alta a mano
        puede tener la barra sin género. Sin la reserva no se encontraría.
        """
        course = build_course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=None,
                    course_rating=71.0,
                    slope_rating=128,
                    holes=build_holes(meters=333),
                ),
                Tee(color=TeeColor.RED, gender=None, course_rating=70.0, slope_rating=120),
            ]
        )

        card = course.hole_card_for(TeeColor.YELLOW, Gender.MALE)

        assert card[0].meters == 333

    def test_cae_a_la_tarjeta_de_referencia_si_la_salida_no_trae_la_suya(self) -> None:
        course = self._course_with_two_cards()

        card = course.hole_card_for(TeeColor.BLUE, Gender.MALE)

        assert [hole.par for hole in card] == [hole.par for hole in course.reference_card]

    def test_el_genero_exacto_gana_a_la_reserva(self) -> None:
        """
        Con la barra valorada por género, cada jugador juega la suya.

        El dominio prohíbe que un mismo color tenga a la vez salida con género y
        sin él (`cannot mix gendered and non-gendered tees`), así que la reserva
        de `tee_for` solo entra cuando el campo no distingue género en absoluto:
        no puede tapar la salida propia de nadie.
        """
        course = self._course_with_two_cards()

        male = course.hole_card_for(TeeColor.YELLOW, Gender.MALE)
        female = course.hole_card_for(TeeColor.RED, Gender.FEMALE)

        assert male[0].meters == 350
        assert female[0].meters == 300

    def test_resuelve_una_salida_other_sin_su_identificador(self) -> None:
        """
        Las "Championship" y las combinadas se guardan como OTHER, y son de las
        que más veces traen tarjeta propia. Ni `MatchPlayer` ni
        `QuickMatchParticipant` guardan el identificador de la salida, así que
        exigirlo aquí las dejaba sin resolver: al jugador se le repartían los
        golpes con su barra —los context builders indexan por (color, género)—
        y se le puntuaba con la tarjeta de referencia.
        """
        champ_pars = list(PAR_72)
        champ_pars[0] = 5
        course = build_course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=140,
                    holes=build_holes(champ_pars, meters=400),
                ),
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=71.0,
                    slope_rating=128,
                    holes=build_holes(meters=350),
                ),
            ]
        )

        card = course.hole_card_for(TeeColor.OTHER, Gender.MALE)

        assert card[0].par == 5
        assert card[0].meters == 400

    def test_con_dos_salidas_other_coge_la_misma_que_el_reparto(self) -> None:
        """
        Dos salidas OTHER del mismo género son legales: `unique_key` las separa
        por identificador (#190). Los context builders indexan por
        `(color, género)` dentro de un bucle, así que se quedan con la última;
        coger aquí la primera repartía los golpes con una barra y puntuaba con
        la otra.
        """
        champ_pars = list(PAR_72)
        champ_pars[0] = 5
        combi_pars = list(PAR_72)
        combi_pars[1] = 3
        course = build_course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=140,
                    holes=build_holes(champ_pars, meters=400),
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinadas",
                    course_rating=71.0,
                    slope_rating=125,
                    holes=build_holes(combi_pars, meters=330),
                ),
            ]
        )

        card = course.hole_card_for(TeeColor.OTHER, Gender.MALE)

        assert course.tee_for(TeeColor.OTHER, Gender.MALE).identifier == "Combinadas"
        assert card[1].par == 3
        assert card[0].meters == 330

    def test_resuelve_una_salida_sin_genero_con_identificador(self) -> None:
        """
        El jugador manda color y género; la salida puede no tener género y sí
        identificador, que es como quedan las OTHER. `find_tee` exige que el
        identificador coincida, así que buscar por ahí se la saltaba y el
        jugador acababa contra la tarjeta del campo.

        Nota: esto cubre la reserva de `tee_for`, no la caída de
        `hole_card_for` a la salida sin género. Esa segunda es defensiva y hoy
        no se puede alcanzar: `_sync_holes_and_tees` copia la tarjeta del campo
        a toda salida que no traiga la suya, así que ninguna se queda sin ella.
        """
        sin_genero_pars = list(PAR_72)
        sin_genero_pars[0] = 5
        course = build_course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=None,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=140,
                    holes=build_holes(sin_genero_pars, meters=400),
                ),
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=71.0,
                    slope_rating=128,
                    holes=build_holes(meters=350),
                ),
            ]
        )

        card = course.hole_card_for(TeeColor.OTHER, Gender.MALE)

        assert card[0].par == 5
        assert card[0].meters == 400
