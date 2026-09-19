"""
Tests de la zona horaria de un campo de golf (BE #305).

La anotación de un partido abre a una hora local del campo, así que el huso vive
donde está la verdad: en el campo, no en la competición. Una competición puede
jugarse en campos de husos distintos, y cada ronda usa el del suyo.

Un campo puede quedarse sin zona —los 13 que no traen coordenadas—, y eso no es
un error: significa que su anotación no se abre sola y hay que pulsar START.
"""

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


def _crear(**kwargs) -> GolfCourse:
    return GolfCourse.create(
        name="Campo de prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
        **kwargs,
    )


class TestZonaHorariaDelCampo:
    def test_se_guarda_la_que_le_den(self):
        assert _crear(timezone="Atlantic/Canary").timezone == "Atlantic/Canary"

    def test_sin_zona_es_valido(self):
        """Un campo sin coordenadas no tiene huso, y eso no impide darlo de alta."""
        assert _crear().timezone is None

    def test_una_zona_que_no_existe_no_se_guarda(self):
        """Guardarla abriría la anotación a una hora que no es la del campo."""
        with pytest.raises(ValueError, match="zona"):
            _crear(timezone="Marte/Olympus")

    def test_tampoco_una_cadena_vacia(self):
        with pytest.raises(ValueError, match="zona"):
            _crear(timezone="")

    def test_convive_con_la_ubicacion(self):
        campo = _crear(
            location=CourseLocation(latitude=28.17084, longitude=-16.7926, city="Guía de Isora"),
            timezone="Atlantic/Canary",
        )

        assert campo.location.city == "Guía de Isora"
        assert campo.timezone == "Atlantic/Canary"
