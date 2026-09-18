"""
El huso de un campo sigue a sus coordenadas (BE #305, `/code-review`).

La zona se deduce de la ubicación al dar de alta el campo. Si luego alguien
corrige las coordenadas y el huso se queda como estaba, pasa lo peor de los dos
mundos: un campo canario dado de alta con coordenadas peninsulares abriría la
anotación una hora antes aunque alguien arregle el dato, y uno de los trece sin
coordenadas se quedaría sin apertura automática para siempre, sin más salida que
tocar la base de datos a mano.
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

PENINSULA = CourseLocation(latitude=40.4637, longitude=-3.7492, city="Madrid")
CANARIAS = CourseLocation(latitude=28.17084, longitude=-16.7926, city="Guía de Isora")


def _tees() -> list[Tee]:
    return [
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
            identifier="Yellow",
            course_rating=70.0,
            slope_rating=125,
        )
    ]


def _holes() -> list[Hole]:
    return [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]


def _campo(location=None, timezone=None) -> GolfCourse:
    return GolfCourse.create(
        name="Campo de prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=_tees(),
        holes=_holes(),
        location=location,
        timezone=timezone,
    )


class TestAlEditarElCampo:
    def test_una_ubicacion_nueva_trae_su_huso(self):
        campo = _campo(PENINSULA, "Europe/Madrid")

        campo.update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            location=CANARIAS,
            timezone="Atlantic/Canary",
        )

        assert campo.timezone == "Atlantic/Canary"

    def test_un_campo_que_no_tenia_huso_lo_gana_al_ponerle_coordenadas(self):
        """Uno de los trece sin coordenadas: con esto deja de necesitar SQL a mano."""
        campo = _campo()
        assert campo.timezone is None

        campo.update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            location=PENINSULA,
            timezone="Europe/Madrid",
        )

        assert campo.timezone == "Europe/Madrid"

    def test_una_edicion_que_no_toca_la_ubicacion_no_pierde_el_huso(self):
        campo = _campo(PENINSULA, "Europe/Madrid")

        campo.update(
            name="Otro nombre",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
        )

        assert campo.timezone == "Europe/Madrid"


class TestConPropuestaDeCambio:
    """Un creador editando un campo ya aprobado genera un clon que revisa un admin."""

    def test_el_clon_hereda_el_huso_del_original(self):
        campo = _campo(PENINSULA, "Europe/Madrid")
        campo.approve()

        clone = campo.apply_update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            is_admin=False,
        )

        assert clone is not None
        assert clone.timezone == "Europe/Madrid", "sin esto el clon nace sin huso"

    def test_y_si_la_propuesta_mueve_el_campo_lleva_el_huso_nuevo(self):
        campo = _campo(PENINSULA, "Europe/Madrid")
        campo.approve()

        clone = campo.apply_update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            is_admin=False,
            location=CANARIAS,
            timezone="Atlantic/Canary",
        )

        assert clone.timezone == "Atlantic/Canary"

    def test_aprobar_la_propuesta_lleva_el_huso_al_original(self):
        campo = _campo(PENINSULA, "Europe/Madrid")
        campo.approve()
        clone = campo.apply_update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            is_admin=False,
            location=CANARIAS,
            timezone="Atlantic/Canary",
        )

        campo.apply_changes_from_clone(clone)

        assert campo.timezone == "Atlantic/Canary", (
            "aprobar unas coordenadas nuevas sin su huso deja la hora vieja"
        )


@pytest.mark.parametrize("zona", ["Marte/Olympus", ""])
def test_una_zona_invalida_tampoco_entra_por_la_edicion(zona):
    campo = _campo(PENINSULA, "Europe/Madrid")

    with pytest.raises(ValueError, match="zona"):
        campo.update(
            name="Campo de prueba",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            tees=_tees(),
            holes=_holes(),
            location=CANARIAS,
            timezone=zona,
        )
