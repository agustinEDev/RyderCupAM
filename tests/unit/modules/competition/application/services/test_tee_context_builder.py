"""
Tests del TeeContextBuilder.

Los dos fallos que motivaron este servicio venian de valorar todas las barras
contra la tarjeta de referencia del campo: `golf_course.reference_card` es solo la de la
PRIMERA barra. De los 800 campos federados importados con mas de una barra con
tarjeta, 25 tienen par distinto entre barras y 56 stroke index distinto.
"""

import logging
from decimal import Decimal

from src.modules.competition.application.services.tee_context_builder import TeeContextBuilder
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


def _card(stroke_indices, pars=None):
    pars = pars or [4] * 18
    return [
        Hole(number=i + 1, par=pars[i], stroke_index=stroke_indices[i]) for i in range(18)
    ]


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
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140, holes=forward),
                Tee(color=TeeColor.YELLOW, gender=Gender.FEMALE, course_rating=79.4,
                    slope_rating=147, holes=backward),
            ],
            holes=forward,
        )

        context = TeeContextBuilder.build(course)

        assert context.holes_for(TeeColor.YELLOW, Gender.MALE)[0] == 1
        # La femenina tiene el orden invertido: su hoyo mas dificil es el 18
        assert context.holes_for(TeeColor.YELLOW, Gender.FEMALE)[0] == 18

    def test_falls_back_to_the_course_order_without_a_card(self):
        course = _course(
            [
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140),
            ]
        )

        context = TeeContextBuilder.build(course)

        assert context.holes_for(TeeColor.YELLOW, Gender.MALE) == context.holes_by_stroke_index

    def test_falls_back_to_a_genderless_tee(self):
        course = _course(
            [Tee(color=TeeColor.WHITE, gender=None, course_rating=74.0, slope_rating=142)]
        )

        context = TeeContextBuilder.build(course)

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
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140, holes=par_72),
                Tee(color=TeeColor.RED, gender=Gender.FEMALE, course_rating=71.0,
                    slope_rating=130, holes=par_70),
            ],
            holes=par_72,
        )

        context = TeeContextBuilder.build(course)

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
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140, holes=forward),
                Tee(color=TeeColor.RED, gender=Gender.FEMALE, course_rating=71.0,
                    slope_rating=130, holes=backward),
            ],
            holes=forward,
        )

        context = TeeContextBuilder.build(course)

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
                Tee(color=TeeColor.ORANGE, gender=Gender.MALE, course_rating=54.9,
                    slope_rating=91, holes=par_58),
            ],
            holes=par_58,
        )
        course.approve()

        context = TeeContextBuilder.build(course)

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
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140),
                Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0,
                    slope_rating=130),
            ]
        )
        # Se fuerza sobre la entidad ya construida: `Tee` no deja crear una
        # barra asi, y es justo lo que hace que este camino sea una reserva
        object.__setattr__(course.tees[0], "course_rating", 30.0)

        context = TeeContextBuilder.build(course)

        assert ("YELLOW", "MALE") not in context.tee_ratings
        assert ("WHITE", "MALE") in context.tee_ratings
    def test_the_warning_says_the_round_cannot_be_generated(self, caplog):
        """
        El aviso decia que los jugadores de esa barra jugarian con su Handicap
        Index, que es lo que pasa en partida rapida y NO aqui. Se corrigio el
        docstring y el aviso de al lado se quedo diciendolo. Ver RyderCupAm#219.
        """
        course = _course(
            [
                Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1,
                    slope_rating=140),
                Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0,
                    slope_rating=130),
            ]
        )
        object.__setattr__(course.tees[0], "course_rating", 30.0)

        with caplog.at_level(logging.WARNING):
            TeeContextBuilder.build(course)

        assert "cannot be rated" in caplog.text
        assert "will not be able to have their round generated" in caplog.text
        # Lo que NO debe decir: eso es lo que hace partida rapida, no esta
        assert "Handicap Index" not in caplog.text
