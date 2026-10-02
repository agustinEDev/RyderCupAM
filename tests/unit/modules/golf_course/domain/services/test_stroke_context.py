"""
Tests del contexto de golpes de un campo, una sola pieza (BE #165).

Competición (`TeeContextBuilder`) y partida rápida (`StrokeContextBuilder`)
traducían el campo cada una a su manera, y las estadísticas valoraban la barra
con una tercera copia. Decidido el 2 oct 2026: una pieza en `golf_course` con la
conducta de competición, que es la más robusta.

Los primeros casos vienen de los tests de competición. Su motivo sigue vigente:
`golf_course.reference_card` es solo la tarjeta de la PRIMERA barra, y de los 800
campos federados con más de una barra con tarjeta, 25 tienen par distinto entre
barras y 56 stroke index distinto.
"""

from decimal import Decimal

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.services.stroke_context import (
    StrokeContextBuilder,
    UnratedTee,
    holes_for_tee,
)
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


def _card(stroke_indices, pars=None):
    pars = pars or [4] * 18
    return [Hole(number=i + 1, par=pars[i], stroke_index=stroke_indices[i]) for i in range(18)]


def _course(tees, holes=None):
    course = GolfCourse.create(
        name="Test",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=tees,
        holes=holes or _card(list(range(1, 19))),
    )
    course.approve()
    return course


class TestPerTeeCard:
    def test_each_tee_keeps_its_own_stroke_index_order(self):
        """
        Given dos barras con stroke index distintos
        When se construye el contexto
        Then cada una conserva su propio orden de dificultad
        """
        forward = _card(list(range(1, 19)))
        backward = _card(list(range(18, 0, -1)))
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=73.1,
                    slope_rating=140,
                    holes=forward,
                ),
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.FEMALE,
                    course_rating=79.4,
                    slope_rating=147,
                    holes=backward,
                ),
            ],
            holes=forward,
        )

        context = StrokeContextBuilder.build(course)

        assert context.holes_for(TeeColor.YELLOW, Gender.MALE)[0] == 1
        # La femenina tiene el orden invertido: su hoyo mas dificil es el 18
        assert context.holes_for(TeeColor.YELLOW, Gender.FEMALE)[0] == 18

    def test_falls_back_to_the_course_order_without_a_card(self):
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140
                ),
            ]
        )

        context = StrokeContextBuilder.build(course)

        assert context.holes_for(TeeColor.YELLOW, Gender.MALE) == context.holes_by_stroke_index

    def test_falls_back_to_a_genderless_tee(self):
        course = _course(
            [Tee(color=TeeColor.WHITE, gender=None, course_rating=74.0, slope_rating=142)]
        )

        context = StrokeContextBuilder.build(course)

        assert (TeeColor.WHITE.value, None) in context.tee_ratings
        assert context.holes_for(TeeColor.WHITE, Gender.MALE) == context.holes_by_stroke_index


class TestPerTeePar:
    def test_each_tee_is_rated_against_its_own_par(self):
        """
        Given una barra con par 70 en un campo cuya tarjeta de referencia es par 72
        When se construye el contexto
        Then esa barra se valora contra 70, no contra 72
        """
        par_72 = _card(list(range(1, 19)), pars=[4] * 18)
        par_70 = _card(list(range(1, 19)), pars=[3, 3] + [4] * 16)
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=73.1,
                    slope_rating=140,
                    holes=par_72,
                ),
                Tee(
                    color=TeeColor.RED,
                    gender=Gender.FEMALE,
                    course_rating=71.0,
                    slope_rating=130,
                    holes=par_70,
                ),
            ],
            holes=par_72,
        )

        context = StrokeContextBuilder.build(course)

        assert context.tee_ratings[("YELLOW", "MALE")].par == 72
        assert context.tee_ratings[("RED", "FEMALE")].par == 70


class TestFoursomesTeamCard:
    """
    En golpe alterno el equipo comparte bola, asi que comparte UNA tarjeta.

    CodeRabbit lo señalo en la PR #208: el reparto de foursomes seguia usando la
    tarjeta de referencia del campo aunque el equipo entero jugase otra barra.
    """

    def test_a_team_on_a_single_tee_uses_that_tees_card(self):
        forward = _card(list(range(1, 19)))
        backward = _card(list(range(18, 0, -1)))
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=73.1,
                    slope_rating=140,
                    holes=forward,
                ),
                Tee(
                    color=TeeColor.RED,
                    gender=Gender.FEMALE,
                    course_rating=71.0,
                    slope_rating=130,
                    holes=backward,
                ),
            ],
            holes=forward,
        )

        context = StrokeContextBuilder.build(course)

        # Un equipo entero desde rojas reparte con el orden de rojas, no con el
        # del campo (que es el de amarillas, la primera barra)
        assert context.holes_for(TeeColor.RED, Gender.FEMALE)[0] == 18
        assert context.holes_by_stroke_index[0] == 1


class TestUnratableTee:
    """
    Una barra que no se puede valorar no debe tumbar la construccion del
    contexto: antes el ValueError subia hasta la API y la ronda se quedaba sin
    poder generar partidos, con un 500. Ver RyderCupAm#219.
    """

    def test_a_pitch_and_putt_tee_is_now_rated(self):
        """
        Given un pitch & putt federado (par 58, CR 54.9, SR 91)
        When se construye el contexto
        Then su barra se valora, en vez de quedarse fuera
        """
        par_58 = _card(list(range(1, 19)), pars=[3] * 14 + [4] * 4)
        course = GolfCourse.create(
            name="Corto",
            country_code=CountryCode("ES"),
            course_type=CourseType.PITCH_AND_PUTT,
            creator_id=UserId.generate(),
            tees=[
                Tee(
                    color=TeeColor.ORANGE,
                    gender=Gender.MALE,
                    course_rating=54.9,
                    slope_rating=91,
                    holes=par_58,
                ),
            ],
            holes=par_58,
        )
        course.approve()

        context = StrokeContextBuilder.build(course)

        assert context.tee_ratings[("ORANGE", "MALE")].par == 58
        assert context.tee_ratings[("ORANGE", "MALE")].course_rating == Decimal("54.9")

    def test_an_unratable_tee_is_left_out_instead_of_raising(self):
        """
        Given una barra cuyo rating no cabe ni en el rango mas ancho
        When se construye el contexto
        Then esa barra se queda fuera y las demas siguen valoradas

        El caso no se da con el catalogo federado —que entra entero en los
        rangos—, pero la reserva tiene que existir: es la que antes lanzaba dos
        veces el mismo error y acababa en un 500.
        """
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140
                ),
                Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0, slope_rating=130),
            ]
        )
        # Se fuerza sobre la entidad ya construida: `Tee` no deja crear una
        # barra asi, y es justo lo que hace que este camino sea una reserva
        object.__setattr__(course.tees[0], "course_rating", 30.0)

        context = StrokeContextBuilder.build(course)

        assert ("YELLOW", "MALE") not in context.tee_ratings
        assert ("WHITE", "MALE") in context.tee_ratings

    def test_an_unratable_tee_is_listed_for_the_caller_to_report(self):
        """
        El aviso lo da cada módulo, con su mensaje y su frecuencia: en
        competición la ronda no se puede generar, en partida rápida se juega con
        el Handicap Index. La pieza solo dice qué barra se quedó fuera.
        """
        course = _course(
            [Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140)]
        )
        object.__setattr__(course.tees[0], "course_rating", 30.0)

        context = StrokeContextBuilder.build(course)

        assert context.unrated_tees == (
            UnratedTee(
                color="YELLOW",
                gender="MALE",
                course_rating=Decimal("30.0"),
                slope_rating=140,
                par=72,
            ),
        )


class TestBehaviourAdoptedFromCompetition:
    """
    Lo que la partida rápida hace distinto desde la unificación (decidido el
    2 oct 2026): antes descartaba la barra y se caía con una tarjeta mal formada.
    """

    def test_a_tee_whose_own_par_cannot_be_rated_uses_the_course_par(self):
        """
        Given una barra con tarjeta propia de par 90, fuera del rango WHS
        When se construye el contexto
        Then se valora contra el par del campo (72) en vez de quedarse fuera
        """
        par_90 = _card(list(range(1, 19)), pars=[5] * 18)
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    course_rating=73.1,
                    slope_rating=140,
                    holes=par_90,
                ),
                Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0, slope_rating=130),
            ]
        )

        context = StrokeContextBuilder.build(course)

        assert context.tee_ratings[("YELLOW", "MALE")].par == 72
        assert context.rated_with_course_par == (("YELLOW", "MALE"),)
        assert context.unrated_tees == ()

    def test_a_malformed_card_falls_back_to_the_course_order(self):
        """
        Given una barra cuya tarjeta trae un stroke index sin valor
        When se construye el contexto
        Then esa barra reparte con el orden del campo, sin lanzar
        """
        backward = _card(list(range(18, 0, -1)))
        course = _course(
            [
                Tee(
                    color=TeeColor.RED,
                    gender=Gender.FEMALE,
                    course_rating=71.0,
                    slope_rating=130,
                    holes=backward,
                ),
            ]
        )
        object.__setattr__(course.tees[0].holes[0], "stroke_index", None)

        context = StrokeContextBuilder.build(course)

        assert context.holes_for(TeeColor.RED, Gender.FEMALE) == context.holes_by_stroke_index


class TestCourseCard:
    """Lo que la partida rápida necesita para puntuar: el par de cada hoyo."""

    def test_par_by_hole_and_course_par_come_from_the_reference_card(self):
        pars = [3, 5] + [4] * 16
        course = _course(
            [Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140)],
            holes=_card(list(range(1, 19)), pars=pars),
        )

        context = StrokeContextBuilder.build(course)

        assert context.par_by_hole[1] == 3
        assert context.par_by_hole[2] == 5
        assert context.course_par == 72

    def test_the_course_order_follows_the_reference_stroke_index(self):
        course = _course(
            [Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140)],
            holes=_card(list(range(18, 0, -1))),
        )

        context = StrokeContextBuilder.build(course)

        assert context.holes_by_stroke_index[0] == 18
        assert context.holes_by_stroke_index[-1] == 1


class TestRatingFor:
    """La valoración de una barra, con la misma reserva que el orden de hoyos."""

    def test_the_exact_tee(self):
        course = _course(
            [
                Tee(
                    color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140
                ),
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.FEMALE,
                    course_rating=79.4,
                    slope_rating=147,
                ),
            ]
        )

        rating = StrokeContextBuilder.build(course).rating_for(TeeColor.YELLOW, Gender.FEMALE)

        assert rating.course_rating == Decimal("79.4")

    def test_falls_back_to_the_genderless_tee_of_that_colour(self):
        course = _course(
            [Tee(color=TeeColor.WHITE, gender=None, course_rating=74.0, slope_rating=142)]
        )

        rating = StrokeContextBuilder.build(course).rating_for(TeeColor.WHITE, Gender.MALE)

        assert rating.course_rating == Decimal("74.0")

    def test_never_the_other_gender(self):
        course = _course(
            [Tee(color=TeeColor.RED, gender=Gender.FEMALE, course_rating=71.0, slope_rating=130)]
        )

        assert StrokeContextBuilder.build(course).rating_for(TeeColor.RED, Gender.MALE) is None

    def test_without_a_colour_there_is_no_rating(self):
        course = _course(
            [Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140)]
        )

        assert StrokeContextBuilder.build(course).rating_for(None, Gender.MALE) is None

    def test_a_repeated_tee_resolves_to_the_last_one(self):
        """
        La misma que resuelve `GolfCourse.tee_for`: el contexto indexa por
        (color, género) y la repetida sobrescribe a la anterior (#190).
        """
        course = _course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=142,
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinada",
                    course_rating=72.0,
                    slope_rating=133,
                ),
            ]
        )

        rating = StrokeContextBuilder.build(course).rating_for(TeeColor.OTHER, Gender.MALE)

        assert rating.course_rating == Decimal("72.0")

    def test_a_repeated_tee_that_cannot_be_rated_gives_no_rating(self):
        """
        Si la última de dos salidas repetidas no se puede valorar, no hay
        valoración: la de la primera iría con la tarjeta de la última, que es
        la que resuelve `GolfCourse.hole_card_for`. Lo encontró la revisión
        local de la B1.
        """
        course = _course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=142,
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinada",
                    course_rating=72.0,
                    slope_rating=133,
                ),
            ]
        )
        object.__setattr__(course.tees[1], "course_rating", 30.0)

        assert StrokeContextBuilder.build(course).rating_for(TeeColor.OTHER, Gender.MALE) is None


class TestRepeatedTeeThatCannotBeRated:
    """
    Dos salidas repetidas (#190) y la última, la que resuelve
    `GolfCourse.hole_card_for`, no se puede valorar. Si quedara la valoración de
    la primera, competición y partida rápida calcularían los golpes con una
    barra y los repartirían con la tarjeta de otra. Decidido el 2 oct 2026: esa
    barra queda sin valorar para todos, como cualquier barra sin valorar.
    """

    def test_no_tee_rating_survives_for_that_key(self):
        course = _course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=142,
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinada",
                    course_rating=72.0,
                    slope_rating=133,
                ),
            ]
        )
        object.__setattr__(course.tees[1], "course_rating", 30.0)

        context = StrokeContextBuilder.build(course)

        assert ("OTHER", "MALE") not in context.tee_ratings
        assert [t.course_rating for t in context.unrated_tees] == [Decimal("30.0")]

    def test_a_repeated_tee_rated_last_keeps_its_rating(self):
        """Al revés no hay problema: la última se valora y es la que manda."""
        course = _course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=142,
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinada",
                    course_rating=72.0,
                    slope_rating=133,
                ),
            ]
        )
        object.__setattr__(course.tees[0], "course_rating", 30.0)

        context = StrokeContextBuilder.build(course)

        assert context.tee_ratings[("OTHER", "MALE")].course_rating == Decimal("72.0")


class TestRepeatedTeeWithoutAValidCard:
    """
    Lo mismo con la tarjeta (CodeRabbit en la #476): si la última de dos salidas
    repetidas no trae tarjeta válida, la de la anterior no vale.
    `GolfCourse.hole_card_for` resuelve la última y cae a la del campo, así que
    el reparto también tiene que caer al orden del campo.
    """

    def test_the_course_order_is_used_instead_of_the_previous_card(self):
        backward = _card(list(range(18, 0, -1)))
        course = _course(
            [
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Championship",
                    course_rating=74.0,
                    slope_rating=142,
                    holes=backward,
                ),
                Tee(
                    color=TeeColor.OTHER,
                    gender=Gender.MALE,
                    identifier="Combinada",
                    course_rating=72.0,
                    slope_rating=133,
                    holes=_card(list(range(1, 19))),
                ),
            ]
        )
        object.__setattr__(course.tees[1].holes[0], "stroke_index", None)

        context = StrokeContextBuilder.build(course)

        assert ("OTHER", "MALE") not in context.holes_by_tee
        assert context.holes_for(TeeColor.OTHER, Gender.MALE) == context.holes_by_stroke_index


class TestHolesForTee:
    """
    La regla de `holes_for`, suelta para quien lleva los datos planos
    (generar y reasignar partidos, que tenían su propia copia).
    """

    BY_TEE: dict = {("YELLOW", "MALE"): [18, 17], ("WHITE", None): [5, 6]}  # noqa: RUF012

    def test_the_exact_tee(self):
        assert holes_for_tee(self.BY_TEE, TeeColor.YELLOW, Gender.MALE, default=[1]) == [18, 17]

    def test_the_genderless_tee(self):
        assert holes_for_tee(self.BY_TEE, TeeColor.WHITE, Gender.FEMALE, default=[1]) == [5, 6]

    def test_without_a_colour_the_default(self):
        assert holes_for_tee(self.BY_TEE, None, Gender.MALE, default=[1]) == [1]

    def test_an_unknown_tee_the_default(self):
        assert holes_for_tee(self.BY_TEE, TeeColor.RED, Gender.MALE, default=[1]) == [1]

    def test_without_cards_at_all_the_default(self):
        """Generar y reasignar llaman sin tarjetas por barra (`None`) en scratch."""
        assert holes_for_tee(None, TeeColor.YELLOW, Gender.MALE, default=[1]) == [1]
