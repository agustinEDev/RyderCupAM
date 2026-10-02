"""
Los avisos de competición sobre el contexto de un campo (BE #165).

La pieza común (`golf_course`) no avisa: dice qué barras se quedaron fuera.
Competición avisa en cada generación, que es puntual, y con su consecuencia
propia: el jugador de esa barra no puede tener la ronda generada.
"""

import logging

from src.modules.competition.application.services.course_context import course_context_for
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


def _course(tees, pars=None):
    holes = [Hole(number=i + 1, par=(pars or [4] * 18)[i], stroke_index=i + 1) for i in range(18)]
    course = GolfCourse.create(
        name="Test",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=tees,
        holes=holes,
    )
    course.approve()
    return course


def _two_tees():
    return [
        Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140),
        Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0, slope_rating=130),
    ]


def test_returns_the_shared_context():
    course = _course(_two_tees())

    context = course_context_for(course)

    assert ("YELLOW", "MALE") in context.tee_ratings
    assert ("WHITE", "MALE") in context.tee_ratings


def test_the_warning_says_the_round_cannot_be_generated(caplog):
    """
    El aviso decía que los jugadores de esa barra jugarían con su Handicap
    Index, que es lo que pasa en partida rápida y NO aquí. Ver RyderCupAm#219.
    """
    course = _course(_two_tees())
    object.__setattr__(course.tees[0], "course_rating", 30.0)

    with caplog.at_level(logging.WARNING):
        course_context_for(course)

    assert "cannot be rated" in caplog.text
    assert "will not be able to have their round generated" in caplog.text
    # Lo que NO debe decir: eso es lo que hace partida rápida, no esta
    assert "Handicap Index" not in caplog.text


def test_warns_on_every_generation(caplog):
    """Generar es puntual: cada vez que se intente, interesa saberlo."""
    course = _course(_two_tees())
    object.__setattr__(course.tees[0], "course_rating", 30.0)

    with caplog.at_level(logging.WARNING):
        course_context_for(course)
        course_context_for(course)

    assert caplog.text.count("cannot be rated") == 2


def test_a_tee_rated_with_the_course_par_leaves_a_debug_trace(caplog):
    par_90 = [Hole(number=i + 1, par=5, stroke_index=i + 1) for i in range(18)]
    tees = _two_tees()
    tees[0] = Tee(
        color=TeeColor.YELLOW,
        gender=Gender.MALE,
        course_rating=73.1,
        slope_rating=140,
        holes=par_90,
    )
    course = _course(tees)

    with caplog.at_level(logging.DEBUG):
        course_context_for(course)

    assert "using the course par" in caplog.text
    assert "cannot be rated" not in caplog.text
