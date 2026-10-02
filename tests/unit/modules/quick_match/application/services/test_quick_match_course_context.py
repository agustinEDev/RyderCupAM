"""
Los avisos de partida rápida sobre el contexto de un campo (BE #165).

La pieza común (`golf_course`) no avisa. Partida rápida avisa UNA vez por campo
y proceso: el detalle de la partida se pide cada 10 segundos mientras se juega,
y avisar en cada llamada llenaría el log con la misma línea toda la vuelta.
"""

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.quick_match.application.services import course_context as module
from src.modules.quick_match.application.services.course_context import course_context_for
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


@pytest.fixture(autouse=True)
def _fresh_reports(monkeypatch):
    """Los campos ya avisados son del proceso: cada test empieza de cero."""
    monkeypatch.setattr(module, "_reported_courses", set())


def _course_with_an_unratable_tee():
    holes = [Hole(number=i + 1, par=4, stroke_index=i + 1) for i in range(18)]
    course = GolfCourse.create(
        name="Test",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            Tee(color=TeeColor.YELLOW, gender=Gender.MALE, course_rating=73.1, slope_rating=140),
            Tee(color=TeeColor.WHITE, gender=Gender.MALE, course_rating=71.0, slope_rating=130),
        ],
        holes=holes,
    )
    course.approve()
    object.__setattr__(course.tees[0], "course_rating", 30.0)
    return course


def test_an_unratable_tee_falls_back_to_the_handicap_index(caplog):
    course = _course_with_an_unratable_tee()

    with caplog.at_level(logging.WARNING):
        context = course_context_for(course)

    assert ("YELLOW", "MALE") not in context.tee_ratings
    assert "Skipping tee YELLOW" in caplog.text
    assert "fall back to their Handicap Index" in caplog.text


def test_warns_once_per_course(caplog):
    course = _course_with_an_unratable_tee()

    with caplog.at_level(logging.WARNING):
        course_context_for(course)
        course_context_for(course)

    assert caplog.text.count("Skipping tee") == 1


def test_a_course_without_holes_is_reported_once(caplog):
    """
    Sin tarjeta no hay stroke index con el que repartir y la partida se juega a
    bruto: degradar en silencio sería indistinguible del éxito.
    """
    course = SimpleNamespace(id=uuid4(), reference_card=[], tees=[])

    with caplog.at_level(logging.WARNING):
        context = course_context_for(course)
        course_context_for(course)

    assert context.holes_by_stroke_index == []
    assert caplog.text.count("has no holes") == 1
